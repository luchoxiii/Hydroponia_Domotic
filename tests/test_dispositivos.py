"""Pruebas para el servicio de dispositivos IoT y endpoints de telemetría."""
from services import dispositivos
from models.dispositivo import Dispositivo


def test_crear_y_listar_dispositivos(app, cultivo_planta):
    """Verifica la creación y listado de dispositivos."""
    with app.app_context():
        disp = dispositivos.crear_dispositivo(
            nombre='ESP32 Invernadero',
            tipo_hardware='ESP32',
            cultivo_id=cultivo_planta,
            ubicacion='Sector A'
        )
        assert disp.id is not None
        assert disp.api_key.startswith('hydro_')
        assert disp.cultivo_id == cultivo_planta

        lista = dispositivos.listar_dispositivos()
        assert len(lista) >= 1
        assert any(d.nombre == 'ESP32 Invernadero' for d in lista)


def test_regenerar_y_eliminar_dispositivo(app, cultivo_planta):
    """Verifica la regeneración de claves y eliminación."""
    with app.app_context():
        disp = dispositivos.crear_dispositivo('Sensor Temp', 'ESP8266', cultivo_planta)
        key_original = disp.api_key

        disp_act = dispositivos.regenerar_api_key(disp.id)
        assert disp_act.api_key != key_original
        assert disp_act.api_key.startswith('hydro_')

        disp_id = disp.id
        assert dispositivos.eliminar_dispositivo(disp_id) is True
        assert dispositivos.obtener_dispositivo(disp_id) is None


def test_api_ping(client, dispositivo_prueba):
    """Verifica el endpoint rápido /api/v1/ping."""
    res = client.get('/api/v1/ping')
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'online'
    assert 'server_time' in data

    # Con API key
    res_key = client.get('/api/v1/ping?api_key=hydro_test_api_key_1234567890')
    assert res_key.status_code == 200
    data_key = res_key.get_json()
    assert data_key['dispositivo'] == 'ESP32 Test'


def test_api_telemetria_sin_api_key(client):
    """Rechaza telemetría si se envía una API key inválida."""
    res = client.post('/api/v1/telemetria', json={
        'api_key': 'clave_inexistente',
        'ph': 6.0
    })
    assert res.status_code == 401
    assert 'inválida' in res.get_json()['error']


def test_api_telemetria_formato_clave_valor(client, dispositivo_prueba):
    """Acepta payload directo {api_key, ph, ec, temperatura...}."""
    payload = {
        'api_key': 'hydro_test_api_key_1234567890',
        'ph': 6.1,
        'ec': 1.1,
        'temperatura': 21.5,
        'humedad': 65.0,
        'nivel_agua': 85.0
    }
    res = client.post('/api/v1/telemetria', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert data['total_lecturas'] == 5
    assert data['dispositivo'] == 'ESP32 Test'


def test_api_telemetria_formato_lista_lecturas(client, dispositivo_prueba):
    """Acepta payload con lista 'lecturas'."""
    payload = {
        'api_key': 'hydro_test_api_key_1234567890',
        'lecturas': [
            {'tipo': 'PH', 'valor': 6.2},
            {'tipo': 'EC', 'valor': 1.0}
        ]
    }
    res = client.post('/api/v1/telemetria', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['total_lecturas'] == 2


def test_api_telemetria_genera_alertas(client, dispositivo_prueba):
    """Verifica que lecturas anómalas por telemetría generen alertas en la respuesta."""
    payload = {
        'api_key': 'hydro_test_api_key_1234567890',
        'ph': 3.5,  # Muy bajo para lechuga (min 5.5) -> Alerta CRÍTICA
        'nivel_agua': 12.0  # < 20% -> Alerta CRÍTICA
    }
    res = client.post('/api/v1/telemetria', json=payload)
    assert res.status_code == 200
    data = res.get_json()
    assert data['alertas_generadas'] >= 2
    assert any(a['tipo'] == 'PH_BAJO' for a in data['alertas'])
    assert any(a['tipo'] == 'NIVEL_AGUA_CRITICO' for a in data['alertas'])


def test_api_update_get_simple(client, dispositivo_prueba):
    """Prueba el endpoint GET ultra-simple para microcontroladores básicos."""
    url = '/api/v1/update?api_key=hydro_test_api_key_1234567890&ph=6.0&temp=22.0&agua=90.0'
    res = client.get(url)
    assert res.status_code == 200
    data = res.get_json()
    assert data['status'] == 'ok'
    assert data['total_lecturas'] == 3


def test_api_dispositivos_json(client, dispositivo_prueba):
    """Devuelve la lista de dispositivos registrados."""
    res = client.get('/api/dispositivos')
    assert res.status_code == 200
    data = res.get_json()
    assert len(data) >= 1
    assert data[0]['nombre'] == 'ESP32 Test'


def test_generar_firmware_esp32_personalizado(app, cultivo_planta):
    """Verifica la generación automática de código C++ (.ino) con API key e IP inyectadas."""
    with app.app_context():
        disp = dispositivos.crear_dispositivo('ESP32 Cama 1', 'ESP32', cultivo_planta)
        codigo = dispositivos.generar_firmware_esp32(
            disp,
            host_url='http://192.168.1.50:5000',
            wifi_ssid='MiInvernadero_WiFi',
            wifi_pass='ClaveSegura123'
        )
        assert '#include <WiFi.h>' in codigo
        assert disp.api_key in codigo
        assert 'http://192.168.1.50:5000/api/v1/telemetria' in codigo
        assert 'MiInvernadero_WiFi' in codigo
        assert 'ClaveSegura123' in codigo


def test_descargar_firmware_rutas(client, dispositivo_prueba):
    """Verifica los endpoints de descarga directa de firmware para Arduino IDE."""
    # Descarga directa GET
    res_get = client.get(f'/dispositivos/{dispositivo_prueba}/descargar-firmware')
    assert res_get.status_code == 200
    assert 'attachment' in res_get.headers.get('Content-Disposition', '')
    assert b'#include <WiFi.h>' in res_get.data

    # Descarga desde formulario POST
    res_post = client.post('/dispositivos/descargar-firmware-form', data={
        'dispositivo_id': str(dispositivo_prueba),
        'wifi_ssid': 'WiFi_Granja',
        'wifi_pass': 'GranjaPass'
    })
    assert res_post.status_code == 200
    assert b'WiFi_Granja' in res_post.data


def test_simulador_virtual_telemetria_1_clic(client, app, cultivo_planta):
    """Verifica que el botón de simulación virtual en 1 clic cree el dispositivo y mande telemetría."""
    res = client.post('/dispositivos/simulador-virtual', data={
        'cultivo_id': str(cultivo_planta),
        'modo': 'normal'
    }, follow_redirects=True)
    assert res.status_code == 200
    assert b'[Simulador]' in res.data or b'Telemetr' in res.data

    # Probar inyección de anomalía
    res_anom = client.post('/dispositivos/simulador-virtual', data={
        'cultivo_id': str(cultivo_planta),
        'modo': 'anomalia'
    }, follow_redirects=True)
    assert res_anom.status_code == 200

