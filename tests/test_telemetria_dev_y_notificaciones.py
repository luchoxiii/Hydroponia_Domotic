"""
Pruebas exhaustivas para:
1. Telemetría Interna del Desarrollador (telemetria_dev):
   - Identificación de quién instala el sistema (SO, Python, ID único).
   - Recolección y medición de consumo (cultivos, lecturas, dispositivos, tamaño SQLite).
   - Avisos discretos al desarrollador ante altas de cultivos, dispositivos y especies.
2. Canales de Notificación del Usuario (notificaciones_usuario):
   - Configuración de Discord Webhook y Telegram personal.
   - Guardado y persistencia en data/notificaciones_usuario.json.
   - Despacho de alertas según severidad (Crítica / Advertencia).
   - Despacho de avisos ante altas de cultivos y dispositivos.
   - Pruebas de conexión (Discord y Telegram).
3. Rutas web /notificaciones en app.py.
"""
from datetime import date
from unittest.mock import patch, MagicMock
import pytest

from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from models.alerta import Alerta
from models.dispositivo import Dispositivo
from services import telemetria_dev, notificaciones_usuario


# ==================== TESTS TELEMETRÍA DESARROLLADOR ====================

def test_obtener_id_instancia():
    """Verifica que se genera y persiste un ID único de instancia con datos del sistema."""
    instancia = telemetria_dev.obtener_id_instancia()
    assert 'instance_id' in instancia
    assert len(instancia['instance_id']) >= 6
    assert 'sistema_operativo' in instancia
    assert 'python_version' in instancia
    assert 'fecha_instalacion' in instancia


def test_registrar_arranque():
    """Verifica el incremento del contador de arranques del sistema."""
    antes = telemetria_dev.obtener_id_instancia().get('total_arranques', 0)
    despues = telemetria_dev.registrar_arranque()
    assert despues['total_arranques'] >= antes + 1
    assert 'ultimo_arranque' in despues


def test_recolectar_metricas_consumo(app, cultivo_planta):
    """Verifica que se miden los consumos del sistema (cultivos, lecturas, BD)."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        lectura = LecturaSensor(cultivo_id=cultivo.id, tipo='PH', valor=6.0)
        db.session.add(lectura)
        db.session.commit()

        metricas = telemetria_dev.recolectar_metricas_consumo()
        assert 'instance_id' in metricas
        assert metricas['cultivos_activos'] >= 1
        assert metricas['cultivos_totales'] >= 1
        assert metricas['lecturas_totales'] >= 1
        assert 'tamano_db_kb' in metricas


@patch('requests.post')
def test_notificar_instalacion_arranque_mock(mock_post, app):
    """Verifica el envío de telemetría de instalación al Telegram del creador."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    with app.app_context():
        with patch.object(app, 'config', {
            **app.config,
            'DEV_TELEGRAM_BOT_TOKEN': 'test_token_123',
            'DEV_TELEGRAM_CHAT_ID': '999888',
            'DEV_TELEMETRIA_ACTIVA': True
        }):
            resultado = telemetria_dev.notificar_instalacion_arranque()
            assert resultado['ok'] is True
            assert mock_post.called
            args, kwargs = mock_post.call_args
            assert 'api.telegram.org' in args[0]
            assert 'test_token_123' in args[0]
            assert kwargs['json']['chat_id'] == '999888'
            assert 'TELEMETRÍA DE INSTALACIÓN' in kwargs['json']['text']


@patch('requests.post')
def test_notificar_alta_dev_mock(mock_post, app):
    """Verifica que el desarrollador recibe un aviso en Telegram cuando hay una nueva alta."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    with app.app_context():
        with patch.object(app, 'config', {
            **app.config,
            'DEV_TELEGRAM_BOT_TOKEN': 'token_dev_456',
            'DEV_TELEGRAM_CHAT_ID': '777666',
            'DEV_TELEMETRIA_ACTIVA': True
        }):
            res = telemetria_dev.notificar_alta_dev(
                'Cultivo', 'Tomates Hidropónicos',
                {'Especie': 'Tomate Cherry', 'Ubicación': 'Torre Vertical 1'}
            )
            assert res['ok'] is True
            assert mock_post.called
            payload = mock_post.call_args[1]['json']
            assert 'NUEVA ALTA REGISTRADA' in payload['text']
            assert 'Tomates Hidropónicos' in payload['text']
            assert 'Torre Vertical 1' in payload['text']


# ==================== TESTS NOTIFICACIONES DE USUARIO ====================

def test_guardar_y_obtener_config_usuario():
    """Verifica guardar y recuperar la configuración de notificaciones del usuario."""
    datos = {
        'discord_activo': True,
        'discord_webhook_url': 'https://discord.com/api/webhooks/123/abc',
        'telegram_activo': True,
        'telegram_token': '111:AAA',
        'telegram_chat_id': '456789',
        'alertas_criticas': True,
        'alertas_advertencias': False,
        'altas_cultivos': True,
        'altas_dispositivos': False
    }
    guardado = notificaciones_usuario.guardar_config_notificaciones(datos)
    assert guardado['discord_activo'] is True
    assert guardado['discord_webhook_url'] == 'https://discord.com/api/webhooks/123/abc'
    assert guardado['alertas_advertencias'] is False

    recuperado = notificaciones_usuario.obtener_config_notificaciones()
    assert recuperado['discord_webhook_url'] == 'https://discord.com/api/webhooks/123/abc'
    assert recuperado['telegram_token'] == '111:AAA'
    assert recuperado['alertas_advertencias'] is False


@patch('requests.post')
def test_enviar_discord_webhook(mock_post):
    """Verifica el formato del Embed enviado a Discord por Webhook."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_post.return_value = mock_resp

    res = notificaciones_usuario.enviar_discord_webhook(
        webhook_url='https://discord.com/api/webhooks/111/xyz',
        titulo='Prueba de Embed',
        descripcion='Descripción de prueba',
        color_hex=3066993,
        campos=[{'name': 'Campo 1', 'value': 'Valor 1'}]
    )
    assert res['ok'] is True
    assert mock_post.called
    kwargs = mock_post.call_args[1]
    assert 'embeds' in kwargs['json']
    assert kwargs['json']['embeds'][0]['title'] == 'Prueba de Embed'
    assert kwargs['json']['embeds'][0]['color'] == 3066993


def test_enviar_discord_webhook_url_invalida():
    """Valida rechazo si la URL no corresponde al dominio oficial de Discord."""
    res = notificaciones_usuario.enviar_discord_webhook('http://malicious.com', 'Titulo', 'Desc')
    assert res['ok'] is False
    assert 'inválida' in res['error'].lower()


@patch('requests.post')
def test_probar_discord(mock_post):
    """Verifica la función de prueba para Discord."""
    mock_resp = MagicMock()
    mock_resp.status_code = 204
    mock_post.return_value = mock_resp

    res = notificaciones_usuario.probar_discord('https://discord.com/api/webhooks/test/token')
    assert res['ok'] is True
    assert mock_post.called


@patch('requests.post')
def test_enviar_y_probar_telegram_usuario(mock_post):
    """Verifica el envío y prueba de mensaje al Telegram configurado por el usuario."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 100}}
    mock_post.return_value = mock_resp

    res = notificaciones_usuario.probar_telegram_usuario('token123', 'chat456')
    assert res['ok'] is True
    assert mock_post.called
    kwargs = mock_post.call_args[1]
    assert kwargs['json']['chat_id'] == 'chat456'
    assert 'Prueba de Conexión de Telegram' in kwargs['json']['text']


@patch('services.notificaciones_usuario.enviar_discord_webhook')
@patch('services.notificaciones_usuario.enviar_telegram_usuario')
def test_despachar_alerta_a_canales_usuario(mock_tg, mock_dc, app, cultivo_planta):
    """Verifica que una alerta se despacha tanto a Discord como a Telegram según configuración."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        # Configurar ambos canales activos
        notificaciones_usuario.guardar_config_notificaciones({
            'discord_activo': True,
            'discord_webhook_url': 'https://discord.com/api/webhooks/test/url',
            'telegram_activo': True,
            'telegram_token': 'bot_token_test',
            'telegram_chat_id': '123456',
            'alertas_criticas': True,
            'alertas_advertencias': True
        })

        alerta = Alerta(
            cultivo_id=cultivo.id,
            tipo='PH_BAJO',
            mensaje='pH crítico: 4.2',
            nivel='CRITICA'
        )

        res = notificaciones_usuario.despachar_alerta(alerta, cultivo=cultivo)
        assert res['ok'] is True
        assert mock_dc.called
        assert mock_tg.called

        # Verificar argumentos Discord
        dc_args = mock_dc.call_args[1]
        assert 'CRITICA' in dc_args['titulo']
        assert dc_args['webhook_url'] == 'https://discord.com/api/webhooks/test/url'

        # Verificar argumentos Telegram
        tg_args = mock_tg.call_args[0]
        assert tg_args[0] == 'bot_token_test'
        assert tg_args[1] == '123456'
        assert 'PH_BAJO' in tg_args[2]


@patch('services.notificaciones_usuario.enviar_discord_webhook')
@patch('services.notificaciones_usuario.enviar_telegram_usuario')
def test_despachar_alta_cultivo(mock_tg, mock_dc, app, cultivo_planta):
    """Verifica despacho de aviso ante alta de cultivo."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        notificaciones_usuario.guardar_config_notificaciones({
            'discord_activo': True,
            'discord_webhook_url': 'https://discord.com/api/webhooks/test/url',
            'telegram_activo': True,
            'telegram_token': 'tok',
            'telegram_chat_id': 'cid',
            'altas_cultivos': True
        })

        res = notificaciones_usuario.despachar_alta_cultivo(cultivo)
        assert res['ok'] is True
        assert mock_dc.called
        assert mock_tg.called
        assert 'Nuevo Cultivo' in mock_dc.call_args[1]['titulo']
        assert 'NUEVO CULTIVO' in mock_tg.call_args[0][2]


@patch('services.notificaciones_usuario.enviar_discord_webhook')
@patch('services.notificaciones_usuario.enviar_telegram_usuario')
def test_despachar_alta_dispositivo(mock_tg, mock_dc, app, cultivo_planta):
    """Verifica despacho de aviso ante alta de nuevo dispositivo IoT."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        notificaciones_usuario.guardar_config_notificaciones({
            'discord_activo': True,
            'discord_webhook_url': 'https://discord.com/api/webhooks/test/url',
            'telegram_activo': True,
            'telegram_token': 'tok',
            'telegram_chat_id': 'cid',
            'altas_dispositivos': True
        })

        disp = Dispositivo(
            nombre='Sensor Sala A',
            tipo_hardware='ESP32',
            api_key='test-key-1234',
            cultivo_id=cultivo.id
        )

        res = notificaciones_usuario.despachar_alta_dispositivo(disp)
        assert res['ok'] is True
        assert mock_dc.called
        assert mock_tg.called
        assert 'Dispositivo IoT' in mock_dc.call_args[1]['titulo']


# ==================== TESTS RUTAS WEB /notificaciones ====================

def test_rutas_web_notificaciones(client):
    """Verifica GET /notificaciones y POST de guardado y pruebas."""
    # 1. GET /notificaciones
    resp = client.get('/notificaciones')
    assert resp.status_code == 200
    assert b'Canales de Notificaci' in resp.data
    assert b'Discord' in resp.data
    assert b'Telegram' in resp.data

    # 2. POST /notificaciones/guardar
    resp_post = client.post('/notificaciones/guardar', data={
        'discord_activo': '1',
        'discord_webhook_url': 'https://discord.com/api/webhooks/test/web',
        'telegram_activo': '1',
        'telegram_token': 'token_formulario',
        'telegram_chat_id': 'chat_formulario',
        'alertas_criticas': '1',
        'alertas_advertencias': '1',
        'altas_cultivos': '1',
        'altas_dispositivos': '1'
    }, follow_redirects=True)
    assert resp_post.status_code == 200
    assert b'guardada exitosamente' in resp_post.data

    # Verificar que los datos se reflejan en el render
    assert b'token_formulario' in resp_post.data
    assert b'chat_formulario' in resp_post.data


@patch('services.notificaciones_usuario.probar_discord')
def test_ruta_probar_discord(mock_probar, client):
    """Verifica endpoint de prueba para Discord."""
    mock_probar.return_value = {'ok': True}
    resp = client.post('/notificaciones/probar-discord', data={
        'discord_webhook_url': 'https://discord.com/api/webhooks/test/test'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'enviado exitosamente a tu canal de Discord' in resp.data


@patch('services.notificaciones_usuario.probar_telegram_usuario')
def test_ruta_probar_telegram(mock_probar, client):
    """Verifica endpoint de prueba para Telegram del usuario."""
    mock_probar.return_value = {'ok': True}
    resp = client.post('/notificaciones/probar-telegram', data={
        'telegram_token': 'abc:123',
        'telegram_chat_id': '99999'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'enviado exitosamente a tu Telegram' in resp.data
