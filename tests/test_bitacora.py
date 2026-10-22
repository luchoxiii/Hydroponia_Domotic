"""
Pruebas de la Bitácora Cifrada e Inmutable de Auditoría en HydroControl.

Objetivo:
- Validar el cifrado simétrico robusto (Fernet AES-128-CBC + HMAC-SHA256).
- Comprobar el encadenamiento criptográfico (Hash Chaining / Ledger).
- Evaluar la detección matemática ante intentos de manipulación o adulteración.
- Verificar las vistas web y la descarga forense del archivo cifrado.
"""
import pytest
import os
from models import db
from services import bitacora


@pytest.fixture(autouse=True)
def limpiar_bitacora_prueba(tmp_path, monkeypatch):
    """Asegura que cada test use un archivo de bitácora temporal y aislado."""
    test_file = str(tmp_path / "bitacora_test.enc")
    monkeypatch.setattr('services.bitacora._ruta_bitacora', lambda: test_file)
    yield
    if os.path.exists(test_file):
        try:
            os.remove(test_file)
        except Exception:
            pass


def test_registro_y_descifrado_evento():
    """Verifica que un evento se guarda cifrado en disco y se descifra fielmente."""
    datos_originales = {
        'ph': 6.2,
        'cultivo': 'Lechuga Canal 1',
        'sensor': 'Sonda pH Pro'
    }

    # 1. Registrar evento
    res = bitacora.registrar_evento(
        tipo='TELEMETRIA_SENSOR',
        categoria='IOT',
        datos=datos_originales,
        severidad='INFO'
    )
    assert res['ok'] is True
    assert res['secuencia'] == 1
    assert len(res['entry_hash']) == 64

    # 2. Verificar que el archivo en disco NO contiene el texto en claro
    ruta = bitacora._ruta_bitacora()
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    assert 'Lechuga Canal 1' not in contenido  # El texto sensible está 100% cifrado

    # 3. Leer y descifrar
    eventos = bitacora.leer_bitacora(limite=10)
    assert len(eventos) == 1
    ev = eventos[0]
    assert ev['tipo'] == 'TELEMETRIA_SENSOR'
    assert ev['categoria'] == 'IOT'
    assert ev['datos']['ph'] == 6.2
    assert ev['datos']['cultivo'] == 'Lechuga Canal 1'


def test_encadenamiento_hashes_y_secuencia():
    """Comprueba el ledger criptográfico y el encadenamiento entre bloques sucesivos."""
    res1 = bitacora.registrar_evento('EVENTO_1', 'SISTEMA', {'paso': 1})
    res2 = bitacora.registrar_evento('EVENTO_2', 'AGRONOMICO', {'paso': 2})
    res3 = bitacora.registrar_evento('EVENTO_3', 'IOT', {'paso': 3})

    assert res1['secuencia'] == 1
    assert res2['secuencia'] == 2
    assert res3['secuencia'] == 3

    ruta = bitacora._ruta_bitacora()
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = [l.strip().split('|') for l in f.readlines()]

    assert len(lineas) == 3
    # Bloque 1 apunta al bloque génesis
    assert 'GENESIS_BLOCK' in lineas[0][2].strip()
    # Bloque 2 prev_hash debe ser el entry_hash del bloque 1
    assert lineas[1][2].strip() == lineas[0][4].strip()
    # Bloque 3 prev_hash debe ser el entry_hash del bloque 2
    assert lineas[2][2].strip() == lineas[1][4].strip()


def test_auditoria_integridad_exitosa():
    """Valida que una bitácora intacta pasa la auditoría criptográfica."""
    for i in range(5):
        bitacora.registrar_evento(f'TEST_{i}', 'SISTEMA', {'indice': i})

    auditoria = bitacora.verificar_integridad_cadena()
    assert auditoria['integra'] is True
    assert auditoria['total_registros'] == 5
    assert 'Auditoría exitosa' in auditoria['mensaje']


def test_deteccion_manipulacion_adulterada():
    """Demuestra que cualquier intento de alterar un byte en el archivo es detectado de inmediato."""
    bitacora.registrar_evento('EVENTO_1', 'SISTEMA', {'v': 100})
    bitacora.registrar_evento('EVENTO_2', 'SISTEMA', {'v': 200})
    bitacora.registrar_evento('EVENTO_3', 'SISTEMA', {'v': 300})

    ruta = bitacora._ruta_bitacora()
    with open(ruta, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    # Modificar un caracter del ciphertext en la línea 2
    partes = lineas[1].split('|')
    cipher_modificado = partes[3][:-2] + "AA"  # Alterar últimos dos bytes base64
    partes[3] = cipher_modificado
    lineas[1] = "|".join(partes)

    with open(ruta, 'w', encoding='utf-8') as f:
        f.writelines(lineas)

    # Auditar: debe fallar infaliblemente
    auditoria = bitacora.verificar_integridad_cadena()
    assert auditoria['integra'] is False
    assert auditoria['linea_corrupta'] == 2


def test_filtrado_por_categoria():
    """Verifica que se pueden filtrar eventos descifrados por su categoría."""
    bitacora.registrar_evento('ARRANQUE', 'SISTEMA', {})
    bitacora.registrar_evento('TEMP_ALTA', 'AGRONOMICO', {})
    bitacora.registrar_evento('ESP32_CONECTADO', 'IOT', {})
    bitacora.registrar_evento('PH_BAJO', 'AGRONOMICO', {})

    todos = bitacora.leer_bitacora()
    assert len(todos) == 4

    agronomicos = bitacora.leer_bitacora(filtro_categoria='AGRONOMICO')
    assert len(agronomicos) == 2
    for ev in agronomicos:
        assert ev['categoria'] == 'AGRONOMICO'

    iot = bitacora.leer_bitacora(filtro_categoria='IOT')
    assert len(iot) == 1
    assert iot[0]['tipo'] == 'ESP32_CONECTADO'


def test_estadisticas_bitacora():
    """Verifica el cálculo de estadísticas de la bitácora."""
    stats = bitacora.estadisticas_bitacora()
    assert stats['total_eventos'] == 0

    bitacora.registrar_evento('TEST', 'SISTEMA', {})
    stats2 = bitacora.estadisticas_bitacora()
    assert stats2['total_eventos'] == 1
    assert stats2['existe'] is True
    assert stats2['tamano_kb'] > 0


def test_rutas_web_bitacora(client):
    """Verifica que el panel web de la bitácora y la descarga operan con éxito."""
    # 1. GET /bitacora
    resp = client.get('/bitacora')
    assert resp.status_code == 200
    assert b'Bit' in resp.data or b'Auditor' in resp.data

    # 2. POST /bitacora/verificar
    resp_verif = client.post('/bitacora/verificar', follow_redirects=True)
    assert resp_verif.status_code == 200
    assert b'Auditor' in resp_verif.data or b'Exitosa' in resp_verif.data

    # 3. GET /bitacora/descargar
    resp_dl = client.get('/bitacora/descargar')
    assert resp_dl.status_code in (200, 302)
    if resp_dl.status_code == 200:
        assert resp_dl.mimetype == 'application/octet-stream'
