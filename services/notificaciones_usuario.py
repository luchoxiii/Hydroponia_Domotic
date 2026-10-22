"""
Servicio de Notificaciones para el Usuario de la Red de Hidroponía.

Permite al usuario configurar sus propios canales personales (Telegram y Discord)
mediante la interfaz web para recibir avisos del estado de sus plantas, hongos,
sensores, desbalances y altas de cultivos.
"""
import json
import os
from datetime import datetime, timezone
import requests

from config import BASEDIR


def _ruta_config():
    return os.path.join(BASEDIR, 'data', 'notificaciones_usuario.json')


def obtener_config_notificaciones():
    """Obtiene la configuración de avisos personalizada por el usuario."""
    ruta = _ruta_config()
    default = {
        'telegram_activo': False,
        'telegram_token': '',
        'telegram_chat_id': '',
        'discord_activo': False,
        'discord_webhook_url': '',
        'alertas_criticas': True,
        'alertas_advertencias': True,
        'altas_cultivos': True,
        'altas_dispositivos': True
    }

    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                default.update(datos)
        except Exception:
            pass

    return default


def guardar_config_notificaciones(datos):
    """Guarda la configuración personalizada del usuario."""
    ruta = _ruta_config()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    config = {
        'telegram_activo': bool(datos.get('telegram_activo')),
        'telegram_token': str(datos.get('telegram_token', '')).strip(),
        'telegram_chat_id': str(datos.get('telegram_chat_id', '')).strip(),
        'discord_activo': bool(datos.get('discord_activo')),
        'discord_webhook_url': str(datos.get('discord_webhook_url', '')).strip(),
        'alertas_criticas': bool(datos.get('alertas_criticas')),
        'alertas_advertencias': bool(datos.get('alertas_advertencias')),
        'altas_cultivos': bool(datos.get('altas_cultivos')),
        'altas_dispositivos': bool(datos.get('altas_dispositivos')),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }

    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    # Sincronizar automáticamente con telegram_config.json para interoperabilidad total
    try:
        ruta_tg = os.path.join(BASEDIR, 'data', 'telegram_config.json')
        if config['telegram_token'] and config['telegram_chat_id']:
            with open(ruta_tg, 'w', encoding='utf-8') as f_tg:
                json.dump({
                    'bot_token': config['telegram_token'],
                    'chat_id': config['telegram_chat_id'],
                    'notificaciones_activas': config['telegram_activo'],
                    'updated_at': config['updated_at']
                }, f_tg, indent=2)
    except Exception:
        pass

    return config


# ==================== ENVÍO A DISCORD ====================

def enviar_discord_webhook(webhook_url, titulo, descripcion, color_hex=3066993, campos=None):
    """
    Envía un mensaje enriquecido (Embed) a Discord mediante su Webhook oficial.
    color_hex: entero decimal del color (ej: 15158332 para rojo, 3066993 para verde).
    """
    if not webhook_url or not webhook_url.startswith('https://discord.com/api/webhooks'):
        return {'ok': False, 'error': 'URL de Webhook de Discord inválida'}

    embed = {
        'title': titulo,
        'description': descripcion,
        'color': color_hex,
        'fields': campos or [],
        'footer': {
            'text': 'HydroControl • Sistema de Monitoreo Hidropónico',
            'icon_url': 'https://cdn-icons-png.flaticon.com/512/628/628283.png'
        },
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    payload = {
        'username': 'HydroControl Monitor',
        'avatar_url': 'https://cdn-icons-png.flaticon.com/512/628/628283.png',
        'embeds': [embed]
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=8)
        if resp.status_code in (200, 204):
            return {'ok': True}
        else:
            return {'ok': False, 'error': f'Discord respondió con error HTTP {resp.status_code}'}
    except Exception as e:
        return {'ok': False, 'error': f'Error al conectar con Discord: {str(e)}'}


def probar_discord(webhook_url):
    """Envía un mensaje de prueba a Discord para comprobar el webhook."""
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    campos = [
        {'name': 'Estado del Enlace', 'value': '✅ Conectado y Operativo', 'inline': True},
        {'name': 'Fecha y Hora', 'value': ahora, 'inline': True},
        {'name': 'Canal', 'value': 'Red Hidropónica & Micológica', 'inline': False}
    ]
    return enviar_discord_webhook(
        webhook_url=webhook_url,
        titulo='🌿 HydroControl - Prueba de Conexión Discord',
        descripcion='¡Excelente! Tu canal de Discord está correctamente vinculado con tu sistema HydroControl. A partir de ahora recibirás alertas y novedades aquí.',
        color_hex=3066993,  # Verde
        campos=campos
    )


# ==================== ENVÍO A TELEGRAM ====================

def enviar_telegram_usuario(token, chat_id, texto):
    """Envía un mensaje al Telegram configurado por el usuario."""
    if not token or not chat_id:
        return {'ok': False, 'error': 'Falta Token o Chat ID de Telegram'}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': texto,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True
    }
    try:
        resp = requests.post(url, json=payload, timeout=8)
        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        if resp.status_code == 200 and data.get('ok'):
            return {'ok': True}
        return {'ok': False, 'error': data.get('description', f'Error HTTP {resp.status_code}')}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def probar_telegram_usuario(token, chat_id):
    """Envía un mensaje de prueba al Telegram del usuario."""
    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    texto = (
        "🌿 <b>HydroControl - Prueba de Conexión de Telegram</b>\n\n"
        "✅ <b>¡Tu bot de Telegram ha sido configurado con éxito!</b>\n"
        "Recibirás aquí las alertas del estado de tus plantas, hongos y depósitos de agua.\n\n"
        f"🕒 <i>Fecha de prueba: {ahora}</i>"
    )
    return enviar_telegram_usuario(token, chat_id, texto)


# ==================== DISPATCHER UNIFICADO DE EVENTOS ====================

def despachar_alerta(alerta, cultivo=None, especie=None):
    """
    Despacha una alerta de sensor a los canales activos del usuario (Telegram y/o Discord).
    """
    cfg = obtener_config_notificaciones()

    # Verificar filtros de severidad
    nivel = (alerta.nivel or 'ADVERTENCIA').upper()
    if nivel == 'CRITICA' and not cfg.get('alertas_criticas'):
        return {'ok': False, 'motivo': 'Alertas críticas desactivadas en preferencias'}
    if nivel == 'ADVERTENCIA' and not cfg.get('alertas_advertencias'):
        return {'ok': False, 'motivo': 'Alertas de advertencia desactivadas en preferencias'}

    cultivo_nombre = cultivo.nombre if cultivo else (alerta.cultivo.nombre if getattr(alerta, 'cultivo', None) else f'Cultivo #{alerta.cultivo_id}')
    esp = especie or (cultivo.especie if cultivo else (alerta.cultivo.especie if getattr(alerta, 'cultivo', None) else None))
    esp_nombre = f" ({esp.nombre_comun})" if esp else ""

    # 1. Enviar a Discord si está activo
    if cfg.get('discord_activo') and cfg.get('discord_webhook_url'):
        color = 15158332 if nivel == 'CRITICA' else 15105570  # Rojo o Naranja
        campos = [
            {'name': '🌿 Cultivo', 'value': f"{cultivo_nombre}{esp_nombre}", 'inline': True},
            {'name': '🏷️ Tipo de Sensor', 'value': alerta.tipo, 'inline': True},
            {'name': '📢 Detalle', 'value': alerta.mensaje, 'inline': False}
        ]
        enviar_discord_webhook(
            webhook_url=cfg['discord_webhook_url'],
            titulo=f"{'🚨' if nivel == 'CRITICA' else '⚠️'} ALERTA {nivel}: {alerta.tipo}",
            descripcion=f"Se detectó un valor fuera del rango óptimo en tu instalación hidropónica.",
            color_hex=color,
            campos=campos
        )

    # 2. Enviar a Telegram si está activo
    if cfg.get('telegram_activo') and cfg.get('telegram_token') and cfg.get('telegram_chat_id'):
        icono = '🚨' if nivel == 'CRITICA' else '⚠️'
        texto = (
            f"<b>{icono} ALERTA {nivel} - HydroControl</b>\n\n"
            f"🌿 <b>Cultivo:</b> {cultivo_nombre}{esp_nombre}\n"
            f"🏷️ <b>Sensor:</b> <code>{alerta.tipo}</code>\n"
            f"📢 <b>Mensaje:</b> {alerta.mensaje}\n\n"
            "👉 <i>Revisa tu sistema hidropónico para calibrar los parámetros.</i>"
        )
        enviar_telegram_usuario(cfg['telegram_token'], cfg['telegram_chat_id'], texto)

    return {'ok': True}


def despachar_alta_cultivo(cultivo):
    """
    Notifica a Discord y/o Telegram cuando se agrega un nuevo cultivo a la red.
    """
    cfg = obtener_config_notificaciones()
    if not cfg.get('altas_cultivos'):
        return {'ok': False, 'motivo': 'Avisos de alta de cultivos desactivados'}

    esp = cultivo.especie
    esp_nombre = esp.nombre_comun if esp else 'Sin especie'
    fecha = cultivo.fecha_siembra.strftime('%d/%m/%Y') if hasattr(cultivo, 'fecha_siembra') and cultivo.fecha_siembra else 'Hoy'

    # Discord
    if cfg.get('discord_activo') and cfg.get('discord_webhook_url'):
        campos = [
            {'name': '🏷️ Nombre', 'value': cultivo.nombre, 'inline': True},
            {'name': '📖 Especie', 'value': esp_nombre, 'inline': True},
            {'name': '📍 Ubicación', 'value': cultivo.ubicacion or 'N/A', 'inline': True},
            {'name': '📅 Siembra', 'value': fecha, 'inline': True}
        ]
        if esp:
            campos.append({
                'name': '🎯 Rangos Ideales',
                'value': f"pH: {esp.ph_min}-{esp.ph_max} | EC: {esp.ec_min}-{esp.ec_max} mS/cm | Temp: {esp.temp_min}-{esp.temp_max}°C",
                'inline': False
            })

        enviar_discord_webhook(
            webhook_url=cfg['discord_webhook_url'],
            titulo='🌱 ¡Nuevo Cultivo en tu Red de Hidroponía!',
            descripcion=f"Se ha dado de alta **{cultivo.nombre}** en el sistema de monitoreo.",
            color_hex=3066993,  # Verde
            campos=campos
        )

    # Telegram
    if cfg.get('telegram_activo') and cfg.get('telegram_token') and cfg.get('telegram_chat_id'):
        texto = (
            "🌱 <b>¡NUEVO CULTIVO DADO DE ALTA!</b>\n\n"
            f"🏷️ <b>Nombre:</b> {cultivo.nombre}\n"
            f"📖 <b>Especie:</b> {esp_nombre}\n"
            f"📍 <b>Ubicación:</b> {cultivo.ubicacion or 'N/A'}\n"
            f"📅 <b>Fecha de Siembra:</b> {fecha}\n\n"
            "✅ <i>El sistema comenzará a registrar sus sensores automáticamente.</i>"
        )
        enviar_telegram_usuario(cfg['telegram_token'], cfg['telegram_chat_id'], texto)

    return {'ok': True}


def despachar_alta_dispositivo(dispositivo):
    """
    Notifica a Discord y/o Telegram cuando se vincula un nuevo sensor o microcontrolador.
    """
    cfg = obtener_config_notificaciones()
    if not cfg.get('altas_dispositivos'):
        return {'ok': False, 'motivo': 'Avisos de alta de dispositivos desactivados'}

    cultivo_nombre = dispositivo.cultivo.nombre if dispositivo.cultivo else 'Sin asignar (global)'

    # Discord
    if cfg.get('discord_activo') and cfg.get('discord_webhook_url'):
        campos = [
            {'name': '📟 Nombre', 'value': dispositivo.nombre, 'inline': True},
            {'name': '⚙️ Hardware', 'value': dispositivo.tipo_hardware, 'inline': True},
            {'name': '🌿 Cultivo', 'value': cultivo_nombre, 'inline': True},
            {'name': '🔑 API Key', 'value': f"`{dispositivo.api_key}`", 'inline': False}
        ]
        enviar_discord_webhook(
            webhook_url=cfg['discord_webhook_url'],
            titulo='🔌 ¡Nuevo Dispositivo IoT Vinculado!',
            descripcion=f"Se conectó la placa **{dispositivo.nombre}** ({dispositivo.tipo_hardware}) a la red.",
            color_hex=3447003,  # Azul
            campos=campos
        )

    # Telegram
    if cfg.get('telegram_activo') and cfg.get('telegram_token') and cfg.get('telegram_chat_id'):
        texto = (
            "🔌 <b>¡NUEVO DISPOSITIVO IOT DADO DE ALTA!</b>\n\n"
            f"📟 <b>Nombre:</b> {dispositivo.nombre}\n"
            f"⚙️ <b>Hardware:</b> {dispositivo.tipo_hardware}\n"
            f"🌿 <b>Cultivo:</b> {cultivo_nombre}\n"
            f"🔑 <b>API Key:</b> <code>{dispositivo.api_key}</code>\n\n"
            "✅ <i>Listo para recibir telemetría de sensores.</i>"
        )
        enviar_telegram_usuario(cfg['telegram_token'], cfg['telegram_chat_id'], texto)

    return {'ok': True}
