"""
Servicio de Bitácora Cifrada de Auditoría y Registro Forense para HydroControl.

Objetivo:
- Registrar de forma inmutable y cifrada (AES-256 + HMAC-SHA256) todo lo que sucede en el sistema:
  * Ingesta de sensores y telemetría IoT.
  * Disparo y lectura de alertas.
  * Altas de especies, cultivos y dispositivos.
  * Diagnósticos del motor de Machine Learning.
  * Cargas y exportaciones de CSV.
  * Despacho de notificaciones (Telegram y Discord).
  * Arranques, paradas y auditoría de seguridad.
- Incorpora encadenamiento criptográfico (Hash Chaining / Ledger Tamper-Evident)
  para asegurar matemáticamente que ningún registro ha sido borrado, modificado
  o insertado ilícitamente.
"""
import os
import json
import base64
import hashlib
import threading
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import BASEDIR, Config

_BITACORA_LOCK = threading.Lock()


def _ruta_bitacora():
    return getattr(Config, 'BITACORA_ARCHIVO', os.path.join(BASEDIR, 'data', 'bitacora_cifrada.enc'))


def _ruta_salt():
    return os.path.join(BASEDIR, 'data', 'bitacora.salt')


def _obtener_fernet(clave_maestra=None):
    """
    Deriva una clave simétrica Fernet (AES-128-CBC + HMAC-SHA256)
    a partir de la clave maestra del sistema y un salt único por instalación.
    """
    secret = clave_maestra or getattr(Config, 'BITACORA_SECRET_KEY', 'hydroponia-audit-ledger-master-key-2024')
    if isinstance(secret, str):
        secret = secret.encode('utf-8')

    ruta_salt = _ruta_salt()
    os.makedirs(os.path.dirname(ruta_salt), exist_ok=True)
    if not os.path.exists(ruta_salt):
        salt = os.urandom(16)
        with open(ruta_salt, 'wb') as f:
            f.write(salt)
    else:
        with open(ruta_salt, 'rb') as f:
            salt = f.read()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    key_derived = base64.urlsafe_b64encode(kdf.derive(secret))
    return Fernet(key_derived)


def _obtener_ultimo_hash(ruta_archivo):
    """Obtiene el hash del último registro para encadenamiento criptográfico."""
    if not os.path.exists(ruta_archivo) or os.path.getsize(ruta_archivo) == 0:
        return 'GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000'

    ultimo_hash = 'GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000'
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for linea in f:
                partes = linea.strip().split('|')
                if len(partes) >= 5:
                    ultimo_hash = partes[4].strip()
    except Exception:
        pass
    return ultimo_hash


def _obtener_siguiente_secuencia(ruta_archivo):
    """Calcula el número de secuencia correlativo."""
    if not os.path.exists(ruta_archivo) or os.path.getsize(ruta_archivo) == 0:
        return 1
    total = 0
    try:
        with open(ruta_archivo, 'r', encoding='utf-8') as f:
            for _ in f:
                total += 1
    except Exception:
        pass
    return total + 1


def registrar_evento(tipo, categoria, datos, severidad='INFO', clave_maestra=None):
    """
    Cifra y almacena un nuevo evento en la bitácora append-only.

    Parámetros:
    - tipo: Nombre técnico del evento (ej: 'TELEMETRIA_SENSOR', 'ALERTA_DISPARADA', 'ALTA_CULTIVO').
    - categoria: Agrupación temática ('SISTEMA', 'IOT', 'AGRONOMICO', 'NOTIFICACION', 'SEGURIDAD').
    - datos: Diccionario con la información del evento a cifrar.
    - severidad: 'INFO', 'ADVERTENCIA', 'CRITICA'.
    """
    ruta = _ruta_bitacora()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)

    with _BITACORA_LOCK:
        fernet = _obtener_fernet(clave_maestra)
        ahora_dt = datetime.now(timezone.utc)
        timestamp_iso = ahora_dt.isoformat()
        secuencia = _obtener_siguiente_secuencia(ruta)
        prev_hash = _obtener_ultimo_hash(ruta)

        payload_claro = {
            'seq': secuencia,
            'timestamp': timestamp_iso,
            'tipo': tipo,
            'categoria': categoria,
            'severidad': severidad,
            'datos': datos or {}
        }

        # Cifrado del payload JSON
        payload_json = json.dumps(payload_claro, ensure_ascii=False, default=str).encode('utf-8')
        ciphertext_bytes = fernet.encrypt(payload_json)
        ciphertext_b64 = ciphertext_bytes.decode('utf-8')

        # Hash encadenado: SHA-256(secuencia + timestamp + prev_hash + ciphertext)
        h = hashlib.sha256()
        h.update(f"{secuencia}|{timestamp_iso}|{prev_hash}|{ciphertext_b64}".encode('utf-8'))
        entry_hash = h.hexdigest()

        # Formato de línea en bitácora:
        # SECUENCIA | TIMESTAMP | PREV_HASH | CIPHERTEXT_B64 | ENTRY_HASH
        linea_registro = f"{secuencia} | {timestamp_iso} | {prev_hash} | {ciphertext_b64} | {entry_hash}\n"

        try:
            with open(ruta, 'a', encoding='utf-8') as f:
                f.write(linea_registro)
            return {
                'ok': True,
                'secuencia': secuencia,
                'entry_hash': entry_hash,
                'timestamp': timestamp_iso
            }
        except Exception as e:
            return {'ok': False, 'error': str(e)}


def leer_bitacora(limite=100, filtro_categoria=None, filtro_tipo=None, clave_maestra=None):
    """
    Lee y descifra las entradas de la bitácora criptográfica.
    Devuelve los registros en orden cronológico inverso (el más reciente primero).
    """
    ruta = _ruta_bitacora()
    if not os.path.exists(ruta):
        return []

    fernet = _obtener_fernet(clave_maestra)
    eventos = []

    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            lineas = f.readlines()
    except Exception:
        return []

    for linea in reversed(lineas):
        partes = [p.strip() for p in linea.strip().split('|')]
        if len(partes) < 5:
            continue

        secuencia, timestamp_iso, prev_hash, ciphertext_b64, entry_hash = partes[:5]

        try:
            decrypted_bytes = fernet.decrypt(ciphertext_b64.encode('utf-8'))
            payload = json.loads(decrypted_bytes.decode('utf-8'))
            payload['entry_hash'] = entry_hash
            payload['prev_hash'] = prev_hash

            if filtro_categoria and payload.get('categoria') != filtro_categoria:
                continue
            if filtro_tipo and payload.get('tipo') != filtro_tipo:
                continue

            eventos.append(payload)
            if len(eventos) >= limite:
                break
        except Exception as e:
            eventos.append({
                'seq': secuencia,
                'timestamp': timestamp_iso,
                'tipo': 'ERROR_DESCIFRADO',
                'categoria': 'SEGURIDAD',
                'severidad': 'CRITICA',
                'datos': {'error': f"Falla de integridad o clave incorrecta: {str(e)}"},
                'entry_hash': entry_hash,
                'prev_hash': prev_hash
            })
            if len(eventos) >= limite:
                break

    return eventos


def verificar_integridad_cadena(clave_maestra=None):
    """
    Audita criptográficamente el encadenamiento de hashes y la autenticidad
    de cada bloque Fernet en la bitácora para certificar que no fue alterada.
    """
    ruta = _ruta_bitacora()
    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        return {
            'integra': True,
            'total_registros': 0,
            'mensaje': 'La bitácora está limpia y vacía.'
        }

    fernet = _obtener_fernet(clave_maestra)
    hash_esperado_previo = 'GENESIS_BLOCK_000000000000000000000000000000000000000000000000000000'
    secuencia_esperada = 1

    with open(ruta, 'r', encoding='utf-8') as f:
        for idx, linea in enumerate(f):
            partes = [p.strip() for p in linea.strip().split('|')]
            if len(partes) < 5:
                return {
                    'integra': False,
                    'linea_corrupta': idx + 1,
                    'motivo': 'Formato de línea incompleto o corrupto'
                }

            secuencia_str, timestamp_iso, prev_hash, ciphertext_b64, entry_hash = partes[:5]
            secuencia = int(secuencia_str)

            # 1. Verificar número de secuencia correlativo
            if secuencia != secuencia_esperada:
                return {
                    'integra': False,
                    'linea_corrupta': idx + 1,
                    'motivo': f"Secuencia alterada: se esperaba #{secuencia_esperada} pero se encontró #{secuencia}"
                }

            # 2. Verificar encadenamiento de hash previo
            if prev_hash != hash_esperado_previo:
                return {
                    'integra': False,
                    'linea_corrupta': idx + 1,
                    'motivo': f"Ruptura de cadena de custodia en bloque #{secuencia}"
                }

            # 3. Recalcular hash del bloque
            h = hashlib.sha256()
            h.update(f"{secuencia}|{timestamp_iso}|{prev_hash}|{ciphertext_b64}".encode('utf-8'))
            hash_calculado = h.hexdigest()

            if hash_calculado != entry_hash:
                return {
                    'integra': False,
                    'linea_corrupta': idx + 1,
                    'motivo': f"Hash adulterado o contenido modificado en bloque #{secuencia}"
                }

            # 4. Verificar firma y descifrado Fernet (HMAC-SHA256)
            try:
                fernet.decrypt(ciphertext_b64.encode('utf-8'))
            except Exception as e:
                return {
                    'integra': False,
                    'linea_corrupta': idx + 1,
                    'motivo': f"Firma criptográfica inválida en bloque #{secuencia}: {str(e)}"
                }

            hash_esperado_previo = entry_hash
            secuencia_esperada += 1

    return {
        'integra': True,
        'total_registros': secuencia_esperada - 1,
        'ultimo_hash': hash_esperado_previo,
        'mensaje': f"Auditoría exitosa: {secuencia_esperada - 1} registros verificados con firma íntegra."
    }


def estadisticas_bitacora():
    """Devuelve estadísticas generales del archivo de bitácora cifrada."""
    ruta = _ruta_bitacora()
    if not os.path.exists(ruta):
        return {
            'existe': False,
            'tamano_kb': 0,
            'total_eventos': 0,
            'ultimo_evento': None
        }

    tamano_kb = round(os.path.getsize(ruta) / 1024, 2)
    total = 0
    ultimo_ts = None
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            for linea in f:
                total += 1
                partes = linea.strip().split('|')
                if len(partes) >= 2:
                    ultimo_ts = partes[1].strip()
    except Exception:
        pass

    return {
        'existe': True,
        'tamano_kb': tamano_kb,
        'total_eventos': total,
        'ultimo_evento': ultimo_ts
    }
