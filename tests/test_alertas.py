"""Pruebas exhaustivas para el motor de generación y evaluación de alertas."""
from models import db
from models.alerta import Alerta
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from services.alertas import (
    verificar_lectura,
    obtener_alertas,
    contar_alertas_no_leidas,
    marcar_como_leida,
    marcar_todas_leidas
)


def test_alerta_ph_en_rango(app, cultivo_planta):
    """pH dentro del rango no debe generar ninguna alerta."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # Lechuga ph_min=5.5, ph_max=6.5
        lectura = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=6.0)
        alertas = verificar_lectura(lectura, cultivo.especie)
        assert len(alertas) == 0


def test_alerta_ph_bajo_advertencia_y_critica(app, cultivo_planta):
    """Verifica umbrales de pH bajo: advertencia si desviación <= 1.0, crítica si > 1.0."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # ph_min=5.5 -> 5.0 es desviación de 0.5 (ADVERTENCIA)
        l1 = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=5.0)
        a1 = verificar_lectura(l1, cultivo.especie)
        assert len(a1) == 1
        assert a1[0].tipo == 'PH_BAJO'
        assert a1[0].nivel == 'ADVERTENCIA'

        # 4.0 es desviación de 1.5 (> 1.0 -> CRITICA)
        l2 = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=4.0)
        a2 = verificar_lectura(l2, cultivo.especie)
        assert len(a2) == 1
        assert a2[0].tipo == 'PH_BAJO'
        assert a2[0].nivel == 'CRITICA'


def test_alerta_ph_alto(app, cultivo_planta):
    """Verifica alertas por pH alto."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # ph_max=6.5 -> 7.0 es ADVERTENCIA
        l1 = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=7.0)
        a1 = verificar_lectura(l1, cultivo.especie)
        assert len(a1) == 1
        assert a1[0].tipo == 'PH_ALTO'
        assert a1[0].nivel == 'ADVERTENCIA'

        # 8.0 es CRITICA (desviación 1.5)
        l2 = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=8.0)
        a2 = verificar_lectura(l2, cultivo.especie)
        assert a2[0].nivel == 'CRITICA'


def test_alerta_ec_conductividad(app, cultivo_planta):
    """Verifica alertas por electroconductividad (EC)."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # ec_min=0.8, ec_max=1.2
        # EC normal
        l_ok = LecturaSensor(cultivo_id=cultivo_planta, tipo='EC', valor=1.0)
        assert len(verificar_lectura(l_ok, cultivo.especie)) == 0

        # EC alta
        l_alta = LecturaSensor(cultivo_id=cultivo_planta, tipo='EC', valor=1.5)
        a_alta = verificar_lectura(l_alta, cultivo.especie)
        assert len(a_alta) == 1
        assert a_alta[0].tipo == 'EC_ALTA'


def test_alerta_temperatura_y_humedad(app, cultivo_planta):
    """Verifica alertas por temperatura y humedad ambiental."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # temp_min=15, temp_max=25
        l_temp_frio = LecturaSensor(cultivo_id=cultivo_planta, tipo='TEMPERATURA', valor=8.0)
        a_frio = verificar_lectura(l_temp_frio, cultivo.especie)
        assert len(a_frio) == 1
        assert a_frio[0].tipo == 'TEMP_BAJA'
        assert a_frio[0].nivel == 'CRITICA'

        # humedad_min=50, humedad_max=70
        l_hum_seca = LecturaSensor(cultivo_id=cultivo_planta, tipo='HUMEDAD', valor=25.0)
        a_hum = verificar_lectura(l_hum_seca, cultivo.especie)
        assert len(a_hum) == 1
        assert a_hum[0].tipo == 'HUMEDAD_BAJA'
        assert a_hum[0].nivel == 'CRITICA'


def test_alerta_nivel_agua_critico(app, cultivo_planta):
    """Nivel de agua < 40% es advertencia, < 20% es crítico."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)

        l_adv = LecturaSensor(cultivo_id=cultivo_planta, tipo='NIVEL_AGUA', valor=35.0)
        a_adv = verificar_lectura(l_adv, cultivo.especie)
        assert a_adv[0].tipo == 'NIVEL_AGUA_BAJO'
        assert a_adv[0].nivel == 'ADVERTENCIA'

        l_crit = LecturaSensor(cultivo_id=cultivo_planta, tipo='NIVEL_AGUA', valor=15.0)
        a_crit = verificar_lectura(l_crit, cultivo.especie)
        assert a_crit[0].tipo == 'NIVEL_AGUA_CRITICO'
        assert a_crit[0].nivel == 'CRITICA'


def test_alerta_hongo_requerimientos_especiales(app, cultivo_hongo):
    """Los hongos requieren alta humedad (80-95%) y baja luz."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_hongo)
        # Seta Ostra: humedad_min=80. 60% es una humedad muy baja para hongos
        l_hum = LecturaSensor(cultivo_id=cultivo_hongo, tipo='HUMEDAD', valor=55.0)
        a_hum = verificar_lectura(l_hum, cultivo.especie)
        assert len(a_hum) == 1
        assert a_hum[0].tipo == 'HUMEDAD_BAJA'
        assert a_hum[0].nivel == 'CRITICA'


def test_gestion_lectura_alertas(app, cultivo_planta):
    """Verifica marcar alertas individuales y todas como leídas."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        l1 = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=3.5)
        l2 = LecturaSensor(cultivo_id=cultivo_planta, tipo='NIVEL_AGUA', valor=10.0)
        verificar_lectura(l1, cultivo.especie)
        verificar_lectura(l2, cultivo.especie)

        assert contar_alertas_no_leidas() == 2
        alertas = obtener_alertas(solo_no_leidas=True)
        assert len(alertas) == 2

        # Marcar una
        marcar_como_leida(alertas[0].id)
        assert contar_alertas_no_leidas() == 1

        # Marcar todas
        marcar_todas_leidas()
        assert contar_alertas_no_leidas() == 0
