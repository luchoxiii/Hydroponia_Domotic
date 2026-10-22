"""Pruebas unitarias para los modelos de datos."""
from datetime import date, datetime, timezone, timedelta
from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from models.alerta import Alerta
from models.dispositivo import Dispositivo


def test_catalogo_default_cargado(app):
    """Verifica que el catálogo inicial cargue al menos 15 especies (plantas y hongos)."""
    with app.app_context():
        total = Especie.query.count()
        plantas = Especie.query.filter_by(categoria='PLANTA').count()
        hongos = Especie.query.filter_by(categoria='HONGO').count()

        assert total >= 15
        assert plantas >= 10
        assert hongos >= 4


def test_modelo_especie_to_dict(app):
    """Verifica la serialización a diccionario de una especie."""
    with app.app_context():
        esp = Especie.query.first()
        d = esp.to_dict()
        assert 'id' in d
        assert 'nombre_comun' in d
        assert 'ph_min' in d
        assert 'ph_max' in d
        assert 'categoria' in d
        assert d['categoria'] in ['PLANTA', 'HONGO']


def test_modelo_cultivo_progreso_y_dias(app, cultivo_planta):
    """Verifica el cálculo de días activo y progreso de un cultivo."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        assert cultivo.dias_activo == 10
        assert cultivo.estado == 'ACTIVO'
        # Lechuga ciclo ~45 días, 10/45 * 100 ~ 22%
        assert 15 <= cultivo.progreso <= 30
        d = cultivo.to_dict()
        assert d['dias_activo'] == 10
        assert d['nombre'] == 'Lechuga Test'


def test_modelo_lectura_sensor(app, cultivo_planta):
    """Verifica el registro y tipos de lecturas de sensores."""
    with app.app_context():
        lectura = LecturaSensor(
            cultivo_id=cultivo_planta,
            tipo='PH',
            valor=6.2
        )
        db.session.add(lectura)
        db.session.commit()

        assert lectura.id is not None
        assert lectura.tipo_info['nombre'] == 'pH'
        assert lectura.tipo_info['icono'] == '🧪'
        d = lectura.to_dict()
        assert d['valor'] == 6.2
        assert d['tipo'] == 'PH'


def test_modelo_alerta_niveles(app, cultivo_planta):
    """Verifica la creación y propiedades de las alertas."""
    with app.app_context():
        alerta = Alerta(
            cultivo_id=cultivo_planta,
            tipo='PH_BAJO',
            mensaje='pH crítico',
            nivel='CRITICA'
        )
        db.session.add(alerta)
        db.session.commit()

        assert alerta.leida is False
        assert alerta.nivel_info['color'] == 'danger'
        d = alerta.to_dict()
        assert d['nivel'] == 'CRITICA'
        assert d['leida'] is False


def test_modelo_dispositivo_status(app, cultivo_planta):
    """Verifica la generación de token y el estado online/offline del dispositivo."""
    with app.app_context():
        key = Dispositivo.generar_api_key()
        assert key.startswith('hydro_')
        assert len(key) > 20

        disp = Dispositivo(
            nombre='Sensor ESP32',
            api_key=key,
            cultivo_id=cultivo_planta
        )
        db.session.add(disp)
        db.session.commit()

        # Sin contacto previo debe figurar offline
        assert disp.online is False

        # Con contacto reciente (hace 2 minutos) debe figurar online
        disp.ultimo_contacto = datetime.now(timezone.utc) - timedelta(minutes=2)
        db.session.commit()
        assert disp.online is True

        # Con contacto antiguo (hace 30 minutos) debe figurar offline
        disp.ultimo_contacto = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.session.commit()
        assert disp.online is False
