"""Pruebas para el servicio y vistas de Telegram (Telemetría y Alertas)."""
import json
from unittest.mock import patch, MagicMock
from models.alerta import Alerta
from models.cultivo import Cultivo
from services import telegram_bot


def test_obtener_y_guardar_config_telegram(tmp_path):
    """Verifica guardar y recuperar la configuración de Telegram."""
    archivo_test = str(tmp_path / "telegram_config.json")
    with patch('services.telegram_bot._ruta_config', return_value=archivo_test):
        # Inicialmente vacío
        cfg = telegram_bot.obtener_config_telegram()
        assert cfg['bot_token'] == ''

        # Guardar nueva config
        telegram_bot.guardar_config_telegram(
            bot_token='123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11',
            chat_id='987654321',
            notificaciones_activas=True
        )

        cfg_guardada = telegram_bot.obtener_config_telegram()
        assert cfg_guardada['bot_token'] == '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11'
        assert cfg_guardada['chat_id'] == '987654321'
        assert cfg_guardada['notificaciones_activas'] is True
        assert cfg_guardada['origen'] == 'archivo'


def test_enviar_mensaje_telegram_exitoso():
    """Verifica el envío exitoso de un mensaje simulando la API de Telegram."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 42}}

    with patch('requests.post', return_value=mock_resp):
        res = telegram_bot.enviar_mensaje_telegram(
            mensaje='Hola HydroControl',
            chat_id='12345',
            bot_token='fake_token'
        )
        assert res['ok'] is True
        assert res['mensaje_id'] == 42


def test_enviar_mensaje_telegram_sin_credenciales():
    """Si no hay token o chat_id, debe devolver error explicativo."""
    with patch.object(telegram_bot, 'obtener_config_telegram', return_value={'bot_token': '', 'chat_id': ''}):
        res = telegram_bot.enviar_mensaje_telegram('Mensaje de prueba')
        assert res['ok'] is False
        assert 'Falta configurar' in res['error']


def test_notificar_alerta_telegram(app, cultivo_planta):
    """Verifica que una alerta genere el formato adecuado para Telegram."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 101}}

    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        alerta = Alerta(
            cultivo_id=cultivo.id,
            tipo='PH_BAJO',
            mensaje='pH bajo: 4.5 (mínimo: 5.5)',
            nivel='CRITICA'
        )

        cfg_mock = {
            'bot_token': 'fake_token',
            'chat_id': '987654',
            'notificaciones_activas': True
        }
        with patch.object(telegram_bot, 'obtener_config_telegram', return_value=cfg_mock):
            with patch('requests.post', return_value=mock_resp) as mock_post:
                res = telegram_bot.notificar_alerta_telegram(alerta, cultivo=cultivo)
                assert res['ok'] is True
                assert mock_post.called
                args, kwargs = mock_post.call_args
                payload = kwargs['json']
                assert 'ALERTA CRITICA' in payload['text']
                assert 'pH bajo: 4.5' in payload['text']


def test_enviar_reporte_telemetria_telegram(app, cultivo_planta):
    """Verifica la generación del reporte de telemetría y salud IA."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 202}}

    with app.app_context():
        cfg_mock = {
            'bot_token': 'fake_token',
            'chat_id': '987654',
            'notificaciones_activas': True
        }
        with patch.object(telegram_bot, 'obtener_config_telegram', return_value=cfg_mock):
            with patch('requests.post', return_value=mock_resp) as mock_post:
                res = telegram_bot.enviar_reporte_telemetria_telegram(cultivo_planta)
                assert res['ok'] is True
                args, kwargs = mock_post.call_args
                texto = kwargs['json']['text']
                assert 'REPORTE DE TELEMETRÍA' in texto
                assert 'Salud del Cultivo' in texto


def test_procesar_comandos_telegram(app, cultivo_planta):
    """Verifica que los comandos interactivos respondan con los datos solicitados."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 303}}

    with app.app_context():
        cfg_mock = {
            'bot_token': 'fake_token',
            'chat_id': '987654',
            'notificaciones_activas': True
        }
        with patch.object(telegram_bot, 'obtener_config_telegram', return_value=cfg_mock):
            with patch('requests.post', return_value=mock_resp) as mock_post:
                # 1. /start
                telegram_bot.procesar_comando_telegram('/start', '987654')
                assert 'Bienvenido al Bot de Telemetría' in mock_post.call_args[1]['json']['text']

                # 2. /status
                telegram_bot.procesar_comando_telegram('/status', '987654')
                assert 'RESUMEN GENERAL' in mock_post.call_args[1]['json']['text']

                # 3. /cultivos
                telegram_bot.procesar_comando_telegram('/cultivos', '987654')
                assert 'Cultivos Activos' in mock_post.call_args[1]['json']['text']

                # 4. /clima
                telegram_bot.procesar_comando_telegram('/clima', '987654')
                assert 'CLIMA EXTERIOR' in mock_post.call_args[1]['json']['text']


def test_rutas_web_telegram(client, cultivo_planta):
    """Verifica las rutas web y endpoints asociados a Telegram."""
    # 1. GET /telegram
    r = client.get('/telegram')
    assert r.status_code == 200
    assert b'Telemetr' in r.data
    assert b'Credenciales de Telegram' in r.data

    # 2. POST /telegram/config
    r_cfg = client.post('/telegram/config', data={
        'bot_token': 'test_token_123',
        'chat_id': '999888',
        'notificaciones_activas': '1'
    }, follow_redirects=True)
    assert r_cfg.status_code == 200
    assert b'guardada correctamente' in r_cfg.data

    # 3. GET /api/v1/telegram/status
    r_stat = client.get('/api/v1/telegram/status')
    assert r_stat.status_code == 200
    datos = r_stat.get_json()
    assert datos['configurado'] is True
    assert datos['notificaciones_activas'] is True
    assert datos['chat_id'] == '999888'

    # 4. POST /cultivos/<id>/enviar-telegram con mock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 99}}

    with patch('requests.post', return_value=mock_resp):
        r_env = client.post(f'/cultivos/{cultivo_planta}/enviar-telegram', follow_redirects=True)
        assert r_env.status_code == 200
        assert b'enviado exitosamente a Telegram' in r_env.data

    # 5. POST /api/v1/telegram/webhook
    with patch('requests.post', return_value=mock_resp):
        r_webhook = client.post('/api/v1/telegram/webhook', json={
            'message': {
                'text': '/status',
                'chat': {'id': 999888}
            }
        })
        assert r_webhook.status_code == 200
        assert r_webhook.get_json()['status'] == 'ok'


def test_notificar_altas_telegram(app, cultivo_planta):
    """Verifica que dar de alta un cultivo, especie o dispositivo envíe mensaje a Telegram."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {'content-type': 'application/json'}
    mock_resp.json.return_value = {'ok': True, 'result': {'message_id': 77}}

    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        cfg_mock = {'bot_token': 'fake_token', 'chat_id': '987654', 'notificaciones_activas': True}

        with patch.object(telegram_bot, 'obtener_config_telegram', return_value=cfg_mock):
            with patch('requests.post', return_value=mock_resp) as mock_post:
                # 1. Alta cultivo
                res_c = telegram_bot.notificar_alta_cultivo(cultivo)
                assert res_c['ok'] is True
                assert 'NUEVO CULTIVO DADO DE ALTA' in mock_post.call_args[1]['json']['text']

                # 2. Alta especie
                from models.especie import Especie
                esp = Especie.query.first()
                res_e = telegram_bot.notificar_alta_especie(esp)
                assert res_e['ok'] is True
                assert 'NUEVA ESPECIE EN CATÁLOGO' in mock_post.call_args[1]['json']['text']

                # 3. Alta dispositivo
                from models.dispositivo import Dispositivo
                disp = Dispositivo(nombre='ESP32 Test', tipo_hardware='ESP32', api_key='hydro_test')
                res_d = telegram_bot.notificar_alta_dispositivo(disp)
                assert res_d['ok'] is True
                assert 'NUEVO DISPOSITIVO IOT DADO DE ALTA' in mock_post.call_args[1]['json']['text']

