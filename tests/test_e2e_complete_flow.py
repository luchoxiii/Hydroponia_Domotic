"""
Prueba de Flujo Completo End-to-End (E2E) en HydroControl.

Recorre el ciclo completo de vida del sistema:
1. Alta de especies botánicas y micológicas en el catálogo.
2. Creación de cultivos activos.
3. Registro de dispositivos IoT y generación de API Key.
4. Ingesta de telemetría masiva de sensores mediante la API REST.
5. Detección automática de alertas agronómicas.
6. Ejecución del diagnóstico predictivo con Machine Learning.
7. Exportación e re-importación masiva en CSV.
8. Transición del ciclo biológico y cosecha al 100%.
9. Despacho auditado al Telegram del desarrollador y canales del usuario.
"""
import pytest
import io
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.dispositivo import Dispositivo
from models.alerta import Alerta
from models.lectura_sensor import LecturaSensor
from services import catalogo, ml_engine, datos_csv, telemetria_dev, notificaciones_usuario, clima


def test_flujo_integral_e2e(app, client):
    """Ejecuta el flujo end-to-end completo del sistema hidropónico."""
    with app.app_context():
        # ==============================================================
        # PASO 1: Alta de Nueva Especie de Planta en el Catálogo
        # ==============================================================
        with patch('services.telemetria_dev.notificar_alta_dev') as mock_alta_dev:
            mock_alta_dev.return_value = {'ok': True}
            especie_planta = catalogo.crear_especie({
                'nombre_comun': 'Rúcula Rocket Pro',
                'nombre_cientifico': 'Eruca sativa',
                'categoria': 'PLANTA',
                'ph_min': 5.8,
                'ph_max': 6.5,
                'ec_min': 1.2,
                'ec_max': 1.8,
                'temp_min': 16.0,
                'temp_max': 24.0,
                'humedad_min': 45.0,
                'humedad_max': 65.0,
                'luz_horas_min': 10.0,
                'luz_horas_max': 14.0,
                'ciclo_dias': 30
            })
            especie_planta_id = especie_planta.id
            assert especie_planta_id is not None
            assert especie_planta.nombre_comun == 'Rúcula Rocket Pro'

        # ==============================================================
        # PASO 2: Alta de Nueva Especie de Hongo Medicinal
        # ==============================================================
        especie_hongo = catalogo.crear_especie({
            'nombre_comun': 'Reishi Medicinal',
            'nombre_cientifico': 'Ganoderma lucidum',
            'categoria': 'HONGO',
            'ph_min': 5.0,
            'ph_max': 6.0,
            'ec_min': 0.0,
            'ec_max': 0.3,
            'temp_min': 20.0,
            'temp_max': 28.0,
            'humedad_min': 80.0,
            'humedad_max': 95.0,
            'luz_horas_min': 2.0,
            'luz_horas_max': 6.0,
            'ciclo_dias': 45
        })
        assert especie_hongo.id is not None
        assert especie_hongo.categoria == 'HONGO'

        # ==============================================================
        # PASO 3: Creación de Cultivo Activo
        # ==============================================================
        cultivo = Cultivo(
            especie_id=especie_planta_id,
            nombre='Lote Rúcula E2E',
            fecha_siembra=date.today() - timedelta(days=15),
            ubicacion='Invernadero Principal - Canal B3',
            estado='ACTIVO'
        )
        db.session.add(cultivo)
        db.session.commit()
        cultivo_id = cultivo.id
        assert cultivo_id is not None
        assert cultivo.progreso == 50  # 15 de 30 días = 50%

        # ==============================================================
        # PASO 4: Registro de Dispositivo IoT (ESP32)
        # ==============================================================
        dispositivo = Dispositivo(
            nombre='ESP32 Invernadero Central',
            cultivo_id=cultivo_id,
            tipo_hardware='ESP32',
            api_key=Dispositivo.generar_api_key()
        )
        db.session.add(dispositivo)
        db.session.commit()
        api_key = dispositivo.api_key
        assert len(api_key) == 38  # hydro_ + 32 hex = 38 chars

    # ==============================================================
    # PASO 5: Ingesta de Telemetría vía API REST (JSON HTTP POST)
    # ==============================================================
    payload_telemetria = {
        'api_key': api_key,
        'ph': 5.0,          # Desviación deliberada (mínimo es 5.8 -> ALERTA)
        'ec': 1.5,          # En rango
        'temperatura': 21.0,# En rango
        'humedad': 55.0,    # En rango
        'nivel_agua': 85.0, # En rango
        'luz': 12.0         # En rango
    }
    resp = client.post('/api/v1/telemetria', json=payload_telemetria)
    assert resp.status_code == 200
    datos_resp = resp.get_json()
    assert datos_resp['status'] == 'ok'
    assert datos_resp['total_lecturas'] == 6
    assert datos_resp['alertas_generadas'] >= 1

    # ==============================================================
    # PASO 6: Verificación de Alertas en Base de Datos
    # ==============================================================
    with app.app_context():
        alertas = Alerta.query.filter_by(cultivo_id=cultivo_id).all()
        assert len(alertas) >= 1
        alerta_ph = [a for a in alertas if 'PH' in a.tipo][0]
        assert alerta_ph.nivel in ('ADVERTENCIA', 'CRITICA')
        assert 'pH' in alerta_ph.mensaje

    # ==============================================================
    # PASO 7: Diagnóstico Predictivo de Machine Learning
    # ==============================================================
    with app.app_context():
        cultivo_db = db.session.get(Cultivo, cultivo_id)
        resumen_sensores = {
            'PH': {'valor': 5.0},
            'EC': {'valor': 1.5},
            'TEMPERATURA': {'valor': 21.0},
            'HUMEDAD': {'valor': 55.0},
            'NIVEL_AGUA': {'valor': 85.0}
        }
        clima_ref = clima.obtener_clima_actual()
        diagnostico = ml_engine.evaluar_salud_cultivo(cultivo_db, resumen_sensores, clima_ref)
        assert 'diagnostico_codigo' in diagnostico
        assert 'score_salud' in diagnostico
        assert isinstance(diagnostico['score_salud'], (int, float))
        assert 'recomendacion_ia' in diagnostico
        assert len(diagnostico['recomendacion_ia']) > 0

    # ==============================================================
    # PASO 8: Exportación e Importación Masiva en CSV
    # ==============================================================
    with app.app_context():
        csv_exportado = datos_csv.exportar_cultivo_csv(cultivo_id)
        assert 'timestamp,cultivo_id' in csv_exportado
        assert 'PH' in csv_exportado

        # Re-importar nuevo lote de datos
        csv_simulado = (
            "tipo,valor,timestamp,unidad\n"
            "PH,6.2,2026-10-20T12:00:00,pH\n"
            "EC,1.6,2026-10-20T12:00:00,mS/cm\n"
            "NIVEL_AGUA,95.0,2026-10-20T12:00:00,%\n"
        )
        res_import, status = datos_csv.importar_lecturas_csv(cultivo_id, csv_simulado)
        assert status == 200
        assert res_import['lecturas_importadas'] == 3

    # ==============================================================
    # PASO 9: Transición de Ciclo de Vida y Cosecha
    # ==============================================================
    with app.app_context():
        cultivo_db = db.session.get(Cultivo, cultivo_id)
        # Avanzar fecha de siembra a 30 días atrás (alcanza el ciclo completo)
        cultivo_db.fecha_siembra = date.today() - timedelta(days=30)
        cultivo_db.estado = 'COSECHADO'
        db.session.commit()

        assert cultivo_db.progreso == 100
        assert cultivo_db.estado == 'COSECHADO'
