"""
Servicio de Telemetría Interna para el Desarrollador / Propietario de HydroControl.

Objetivo:
- Saber quién instala la aplicación (SO, versión de Python, identificador único de instancia).
- Medir el consumo y adopción del sistema (número de cultivos creados, lecturas procesadas,
  dispositivos IoT conectados, alertas generadas y tamaño de la base de datos).
- Canal: Telegram Privado del Desarrollador (oculto para el usuario final).
"""
import json
import os
import platform
import uuid
from datetime import datetime, timezone
import requests
from flask import current_app

from config import BASEDIR


def _ruta_instancia():
    return os.path.join(BASEDIR, 'data', 'instancia_dev.json')


def obtener_id_instancia():
    """
    Obtiene o genera un identificador único persistente para esta instalación
    del software, registrando la fecha de instalación inicial.
    """
    ruta = _ruta_instancia()
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                return datos
        except Exception:
            pass

    # Primera instalación
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    datos = {
        'instance_id': str(uuid.uuid4())[:8],
        'fecha_instalacion': datetime.now(timezone.utc).isoformat(),
        'sistema_operativo': f"{platform.system()} {platform.release()} ({platform.machine()})",
        'python_version': platform.python_version(),
        'nombre_equipo': platform.node(),
        'total_arranques': 0
    }
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2)
    except Exception:
        pass
    return datos


def registrar_arranque():
    """Incrementa el contador de arranques de la instancia."""
    ruta = _ruta_instancia()
    datos = obtener_id_instancia()
    datos['total_arranques'] = datos.get('total_arranques', 0) + 1
    datos['ultimo_arranque'] = datetime.now(timezone.utc).isoformat()
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2)
    except Exception:
        pass
    return datos


def recolectar_metricas_consumo():
    """
    Recolecta estadísticas de uso y consumo del sistema en la máquina instalada.
    """
    instancia = obtener_id_instancia()

    # Tamaño de la base de datos SQLite
    db_path = os.path.join(BASEDIR, 'data', 'hydroponia.db')
    db_size_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.exists(db_path) else 0

    metricas = {
        'instance_id': instancia.get('instance_id', 'unknown'),
        'fecha_instalacion': instancia.get('fecha_instalacion', ''),
        'total_arranques': instancia.get('total_arranques', 1),
        'sistema_operativo': instancia.get('sistema_operativo', platform.platform()),
        'python_version': instancia.get('python_version', platform.python_version()),
        'tamano_db_kb': db_size_kb,
        'cultivos_activos': 0,
        'cultivos_totales': 0,
        'dispositivos_iot': 0,
        'lecturas_totales': 0,
        'alertas_totales': 0
    }

    try:
        from models.cultivo import Cultivo
        from models.lectura_sensor import LecturaSensor
        from models.alerta import Alerta
        from models.dispositivo import Dispositivo

        metricas['cultivos_totales'] = Cultivo.query.count()
        metricas['cultivos_activos'] = Cultivo.query.filter_by(estado='ACTIVO').count()
        metricas['dispositivos_iot'] = Dispositivo.query.count()
        metricas['lecturas_totales'] = LecturaSensor.query.count()
        metricas['alertas_totales'] = Alerta.query.count()
    except Exception:
        pass

    return metricas


def obtener_credenciales_dev():
    """
    Obtiene las credenciales privadas del desarrollador (desde variables de entorno o config).
    """
    token = ''
    chat_id = ''
    activa = True

    try:
        if current_app:
            token = current_app.config.get('DEV_TELEGRAM_BOT_TOKEN', '')
            chat_id = str(current_app.config.get('DEV_TELEGRAM_CHAT_ID', ''))
            activa = current_app.config.get('DEV_TELEMETRIA_ACTIVA', True)
    except RuntimeError:
        pass

    if not token:
        token = os.environ.get('DEV_TELEGRAM_BOT_TOKEN', '')
    if not chat_id:
        chat_id = os.environ.get('DEV_TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        # Fallback a TELEGRAM_BOT_TOKEN si se definió como variable principal del servidor
        token = token or os.environ.get('TELEGRAM_BOT_TOKEN', '')
        chat_id = chat_id or os.environ.get('TELEGRAM_CHAT_ID', '')

    return {
        'token': (token or '').strip(),
        'chat_id': (chat_id or '').strip(),
        'activa': bool(activa) and bool(token and chat_id)
    }


def notificar_instalacion_arranque():
    """
    Envía a Telegram del desarrollador un reporte con datos de instalación y consumo.
    Se ejecuta silenciosamente en segundo plano sin interrumpir la aplicación.
    """
    creds = obtener_credenciales_dev()
    if not creds['activa']:
        return {'ok': False, 'motivo': 'Telemetría de desarrollador no configurada o inactiva'}

    registrar_arranque()
    m = recolectar_metricas_consumo()
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    texto = (
        "🛠️ <b>TELEMETRÍA DE INSTALACIÓN & CONSUMO - HydroControl</b>\n\n"
        f"🆔 <b>ID de Instancia:</b> <code>{m['instance_id']}</code>\n"
        f"💻 <b>SO / Entorno:</b> {m['sistema_operativo']}\n"
        f"🐍 <b>Python:</b> {m['python_version']}\n"
        f"🚀 <b>Total Arranques:</b> {m['total_arranques']}\n\n"
        "📊 <b>Métricas de Consumo y Uso:</b>\n"
        f"• 🌱 <b>Cultivos:</b> {m['cultivos_activos']} activos ({m['cultivos_totales']} totales)\n"
        f"• 🔌 <b>Dispositivos IoT:</b> {m['dispositivos_iot']}\n"
        f"• 📡 <b>Lecturas Registradas:</b> {m['lecturas_totales']}\n"
        f"• 🚨 <b>Alertas Generadas:</b> {m['alertas_totales']}\n"
        f"• 💾 <b>Tamaño BD SQLite:</b> {m['tamano_db_kb']} KB\n\n"
        f"🕒 <i>Reportado: {ahora}</i>"
    )

    url = f"https://api.telegram.org/bot{creds['token']}/sendMessage"
    payload = {
        'chat_id': creds['chat_id'],
        'text': texto,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        return {'ok': resp.status_code == 200, 'status': resp.status_code}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def notificar_alta_dev(tipo_alta, nombre, info_extra=None):
    """
    Notifica al desarrollador en su Telegram privado cuando una instancia da de alta
    un nuevo cultivo, dispositivo IoT o especie.
    """
    creds = obtener_credenciales_dev()
    if not creds['activa']:
        return {'ok': False, 'motivo': 'Inactiva'}

    instancia = obtener_id_instancia()
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    lineas_extra = ""
    if info_extra and isinstance(info_extra, dict):
        lineas_extra = "\n".join([f"• <b>{k}:</b> {v}" for k, v in info_extra.items()])
        lineas_extra = f"\n\n📋 <b>Detalles:</b>\n{lineas_extra}"

    texto = (
        f"📢 <b>NUEVA ALTA REGISTRADA - HydroControl</b>\n\n"
        f"🆔 <b>Instancia:</b> <code>{instancia.get('instance_id', 'unknown')}</code> ({instancia.get('nombre_equipo', '')})\n"
        f"🏷️ <b>Tipo de Alta:</b> {tipo_alta}\n"
        f"✨ <b>Elemento:</b> <b>{nombre}</b>"
        f"{lineas_extra}\n\n"
        f"🕒 <i>{ahora}</i>"
    )

    url = f"https://api.telegram.org/bot{creds['token']}/sendMessage"
    payload = {
        'chat_id': creds['chat_id'],
        'text': texto,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        return {'ok': resp.status_code == 200}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

