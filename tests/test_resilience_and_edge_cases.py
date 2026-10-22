"""
Pruebas de Resiliencia, Tolerancia a Fallos y Casos Límite en HydroControl.

Objetivo:
- Verificar el comportamiento ante fallos de red externos (Telegram, Discord, Open-Meteo).
- Evaluar robustez ante entradas anómalas, valores extremos y ataques de inyección básica.
- Comprobar la tolerancia a archivos corruptos o malformados en CSV.
"""
import pytest
import io
import requests
from unittest.mock import patch, MagicMock
from models import db
from models.cultivo import Cultivo
from models.dispositivo import Dispositivo
from models.lectura_sensor import LecturaSensor
from services import clima, ml_engine, datos_csv, telemetria_dev, notificaciones_usuario


# ==================== 1. RESILIENCIA DE RED EXTERNA ====================

def test_clima_falla_conexion_red(app):
    """Verifica que el servicio de clima maneja desconexiones de red sin romper la app."""
    with app.app_context():
        # Simular fallo de conexión a Open-Meteo
        with patch('requests.get', side_effect=requests.exceptions.ConnectionError("Sin Internet")):
            res = clima.obtener_clima_actual(forzar=True)
            assert 'Simulador' in res['fuente'] or 'Agroclimático' in res['fuente']
            assert 'temp_externa' in res
            assert 'humedad_externa' in res


def test_clima_timeout_red(app):
    """Verifica que un timeout prolongado en Open-Meteo activa el estimador resiliente."""
    with app.app_context():
        with patch('requests.get', side_effect=requests.exceptions.Timeout("Timeout")):
            res = clima.obtener_clima_actual(forzar=True)
            assert 'Simulador' in res['fuente'] or 'Agroclimático' in res['fuente']
            assert 'temp_externa' in res


def test_telegram_dev_falla_servidor_500(app):
    """Verifica que si la API de Telegram devuelve error 500, no interrumpe el flujo."""
    with app.app_context():
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch('requests.post', return_value=mock_resp):
            res = telemetria_dev.notificar_instalacion_arranque()
            assert res['ok'] is False


def test_telegram_dev_excepcion_red(app):
    """Verifica que una excepción de socket en Telegram se captura de forma segura."""
    with app.app_context():
        with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Socket closed")):
            res = telemetria_dev.notificar_alta_dev("Cultivo", "Test")
            assert res['ok'] is False
            assert 'error' in res


def test_discord_webhook_error_http(app):
    """Verifica que un Webhook inválido de Discord se reporta sin levantar excepción no controlada."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    with patch('requests.post', return_value=mock_resp):
        res = notificaciones_usuario.enviar_discord_webhook(
            "https://discord.com/api/webhooks/invalid/token",
            "Test Titulo",
            "Test Descripcion"
        )
        assert res['ok'] is False
        assert 'error' in res


def test_discord_webhook_timeout(app):
    """Verifica timeout en Webhook de Discord."""
    with patch('requests.post', side_effect=requests.exceptions.Timeout("Timeout")):
        res = notificaciones_usuario.enviar_discord_webhook(
            "https://discord.com/api/webhooks/test",
            "Test Titulo",
            "Test Descripcion"
        )
        assert res['ok'] is False
        assert 'error' in res


# ==================== 2. CASOS LÍMITE DE SENSORES Y ENTRADAS ====================

def test_api_telemetria_sin_api_key(client):
    """Rechaza peticiones a la API sin credenciales de autenticación."""
    resp = client.post('/api/v1/telemetria', json={'ph': 6.0})
    assert resp.status_code in (400, 401)
    datos = resp.get_json()
    assert 'error' in datos


def test_api_telemetria_api_key_inexistente(client):
    """Rechaza claves API inexistentes."""
    resp = client.post('/api/v1/telemetria', json={'api_key': 'clave_falsa_123', 'ph': 6.0})
    assert resp.status_code == 401


def test_api_update_get_sin_api_key(client):
    """Rechaza endpoint GET /api/v1/update sin clave."""
    resp = client.get('/api/v1/update?ph=6.0')
    assert resp.status_code in (400, 401)


def test_api_telemetria_valores_no_numericos(client, app, cultivo_planta):
    """Comprueba que strings o valores no numéricos se ignoran sin quebrar la API."""
    with app.app_context():
        disp = Dispositivo(
            nombre='Sensor Edge',
            cultivo_id=cultivo_planta,
            api_key=Dispositivo.generar_api_key()
        )
        db.session.add(disp)
        db.session.commit()
        api_key = disp.api_key

    # Enviar valores corruptos (strings en lugar de float)
    payload = {
        'api_key': api_key,
        'ph': 'valor_invalido',
        'temperatura': 'veinticinco_grados',
        'ec': 1.5  # Solo este es válido
    }
    resp = client.post('/api/v1/telemetria', json=payload)
    assert resp.status_code == 200
    datos = resp.get_json()
    assert datos['total_lecturas'] == 1  # Solo se guardó EC


def test_api_telemetria_cuerpo_vacio_o_invalido(client, app, cultivo_planta):
    """Verifica manejo de peticiones vacías o sin JSON."""
    with app.app_context():
        disp = Dispositivo(
            nombre='Sensor Edge 2',
            cultivo_id=cultivo_planta,
            api_key=Dispositivo.generar_api_key()
        )
        db.session.add(disp)
        db.session.commit()
        api_key = disp.api_key

    resp = client.post('/api/v1/telemetria', data="Esto no es un JSON", content_type="text/plain")
    assert resp.status_code in (400, 401)


# ==================== 3. TOLERANCIA A CSV CORRUPTOS ====================

def test_importar_csv_archivo_vacio(app, cultivo_planta):
    """Verifica manejo de archivo CSV completamente vacío (0 bytes)."""
    with app.app_context():
        f = io.BytesIO(b"")
        res, status = datos_csv.importar_lecturas_csv(cultivo_planta, f.getvalue())
        assert status == 400
        assert 'error' in res


def test_importar_csv_sin_cabecera_requerida(app, cultivo_planta):
    """Verifica manejo de CSV con columnas incorrectas."""
    with app.app_context():
        contenido = b"columna_a,columna_b\n1,2\n3,4"
        res, status = datos_csv.importar_lecturas_csv(cultivo_planta, contenido)
        assert status == 200
        assert res['lecturas_importadas'] == 0


def test_importar_csv_lineas_parcialmente_corruptas(app, cultivo_planta):
    """Verifica que líneas con valores corruptos se descartan sin abortar el resto."""
    with app.app_context():
        contenido = (
            b"tipo,valor,timestamp,unidad\n"
            b"PH,6.1,2026-10-19T10:00:00,pH\n"
            b"EC,no_es_un_numero,2026-10-19T10:00:00,mS/cm\n"
            b"TEMPERATURA,22.4,2026-10-19T10:00:00,\xc2\xb0C\n"
        )
        res, status = datos_csv.importar_lecturas_csv(cultivo_planta, contenido)
        assert status == 200
        assert res['lecturas_importadas'] == 2  # PH y TEMPERATURA pasaron, EC se ignoró


# ==================== 4. INTEGRIDAD DE MACHINE LEARNING ====================

def test_ml_con_todas_las_variables_en_cero(app, cultivo_planta):
    """Verifica que el modelo evalúa correctamente un escenario extremo con sensores en 0."""
    with app.app_context():
        cultivo = db.session.get(Cultivo, cultivo_planta)
        resumen_cero = {
            'PH': {'valor': 0.0},
            'EC': {'valor': 0.0},
            'TEMPERATURA': {'valor': 0.0},
            'HUMEDAD': {'valor': 0.0},
            'NIVEL_AGUA': {'valor': 0.0}
        }
        clima_ref = {'temp_externa': 20.0, 'humedad_externa': 50.0}
        diagnostico = ml_engine.evaluar_salud_cultivo(cultivo, resumen_cero, clima_ref)
        assert 'diagnostico_codigo' in diagnostico
        assert 'score_salud' in diagnostico
        assert diagnostico['score_salud'] <= 60
        assert 'recomendacion_ia' in diagnostico
        assert len(diagnostico['recomendacion_ia']) > 0


def test_ml_cache_ram_consistencia(app, cultivo_planta):
    """Verifica que las inferencias consecutivas son consistentes y usan la caché en RAM."""
    with app.app_context():
        cultivo = db.session.get(Cultivo, cultivo_planta)
        resumen = {
            'PH': {'valor': 6.0},
            'EC': {'valor': 1.4},
            'TEMPERATURA': {'valor': 22.0},
            'HUMEDAD': {'valor': 65.0},
            'NIVEL_AGUA': {'valor': 90.0}
        }
        clima_ref = {'temp_externa': 20.0, 'humedad_externa': 50.0}
        
        diag1 = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_ref)
        diag2 = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_ref)
        
        assert diag1['diagnostico_codigo'] == diag2['diagnostico_codigo']
        assert diag1['score_salud'] == diag2['score_salud']
