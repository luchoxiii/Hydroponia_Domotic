"""
Servicio de Integración y Telemetría por Telegram para HydroControl.

Permite:
1. Enviar alertas en tiempo real al chat o canal de Telegram configurado.
2. Enviar reportes completos de telemetría y diagnóstico IA de cultivos.
3. Probar la conexión del bot con un solo clic.
4. Procesar comandos interactivos (/start, /status, /telemetria, /clima, /alertas) vía Webhook o Polling.
"""
import json
import os
from datetime import datetime, timezone
import requests
from flask import current_app

from config import BASEDIR


def _ruta_config():
    """Ruta al archivo local de configuración de Telegram."""
    return os.path.join(BASEDIR, 'data', 'telegram_config.json')


def obtener_config_telegram():
    """
    Obtiene la configuración de Telegram (Token, Chat ID, Notificaciones).
    Prioridad:
      1. Archivo local data/telegram_config.json (guardado desde la interfaz web).
      2. current_app.config o variables de entorno del sistema.
    """
    ruta = _ruta_config()
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                datos = json.load(f)
                return {
                    'bot_token': datos.get('bot_token', '').strip(),
                    'chat_id': str(datos.get('chat_id', '')).strip(),
                    'notificaciones_activas': bool(datos.get('notificaciones_activas', True)),
                    'origen': 'archivo'
                }
        except Exception:
            pass

    # Fallback a configuración de Flask / entorno
    token = ''
    chat_id = ''
    notif = True
    try:
        if current_app:
            token = current_app.config.get('TELEGRAM_BOT_TOKEN', '')
            chat_id = str(current_app.config.get('TELEGRAM_CHAT_ID', ''))
            notif = current_app.config.get('TELEGRAM_NOTIFICACIONES', True)
    except RuntimeError:
        # Fuera de contexto de Flask
        token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
        notif = os.environ.get('TELEGRAM_NOTIFICACIONES', 'true').lower() in ('1', 'true', 'yes')

    return {
        'bot_token': (token or '').strip(),
        'chat_id': (chat_id or '').strip(),
        'notificaciones_activas': bool(notif),
        'origen': 'entorno' if (token or chat_id) else 'no_configurado'
    }


def guardar_config_telegram(bot_token, chat_id, notificaciones_activas=True):
    """Guarda la configuración de Telegram en data/telegram_config.json."""
    ruta = _ruta_config()
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    datos = {
        'bot_token': str(bot_token).strip(),
        'chat_id': str(chat_id).strip(),
        'notificaciones_activas': bool(notificaciones_activas),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)

    # Sincronizar automáticamente con data/notificaciones_usuario.json para Bot 2
    try:
        ruta_u = os.path.join(BASEDIR, 'data', 'notificaciones_usuario.json')
        datos_u = {}
        if os.path.exists(ruta_u):
            with open(ruta_u, 'r', encoding='utf-8') as f_u:
                datos_u = json.load(f_u)
        datos_u['telegram_token'] = str(bot_token).strip()
        datos_u['telegram_chat_id'] = str(chat_id).strip()
        datos_u['telegram_activo'] = bool(notificaciones_activas)
        datos_u['updated_at'] = datos['updated_at']
        with open(ruta_u, 'w', encoding='utf-8') as f_u:
            json.dump(datos_u, f_u, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return datos


def enviar_mensaje_telegram(mensaje, parse_mode='HTML', chat_id=None, bot_token=None):
    """
    Envía un mensaje a Telegram mediante la API HTTP oficial de Bot de Telegram.
    Retorna un diccionario {'ok': bool, 'mensaje': str, ...}.
    """
    cfg = obtener_config_telegram()
    token = bot_token or cfg.get('bot_token')
    destino_chat = chat_id or cfg.get('chat_id')

    if not token or not destino_chat:
        return {
            'ok': False,
            'error': 'Falta configurar el Bot Token o el Chat ID de Telegram'
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': destino_chat,
        'text': mensaje,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True
    }

    try:
        resp = requests.post(url, json=payload, timeout=8)
        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        if resp.status_code == 200 and data.get('ok'):
            return {'ok': True, 'mensaje_id': data.get('result', {}).get('message_id')}
        else:
            descripcion = data.get('description', f'Error HTTP {resp.status_code}')
            return {'ok': False, 'error': f'Telegram rechazó el envío: {descripcion}'}
    except requests.exceptions.Timeout:
        return {'ok': False, 'error': 'Tiempo de espera agotado al conectar con api.telegram.org'}
    except Exception as e:
        return {'ok': False, 'error': f'Excepción al enviar a Telegram: {str(e)}'}


def probar_conexion_telegram(bot_token=None, chat_id=None):
    """Envía un mensaje de prueba al chat configurado para verificar credenciales."""
    cfg = obtener_config_telegram()
    token = bot_token or cfg.get('bot_token')
    chat = chat_id or cfg.get('chat_id')

    if not token:
        return {'ok': False, 'error': 'Debes ingresar un Bot Token (ej: 123456789:ABCdef...)'}
    if not chat:
        return {'ok': False, 'error': 'Debes ingresar un Chat ID (ej: 987654321)'}

    ahora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    texto = (
        "🌿 <b>HydroControl - Notificaciones de Hidroponía</b>\n\n"
        "✅ <b>¡Conexión establecida con éxito!</b>\n"
        "Tu bot de telemetría y alertas para hidroponía y hongos está activo y vinculado a este chat.\n\n"
        f"🕒 <i>Fecha de prueba: {ahora}</i>\n"
        "🌱 <i>HydroControl IoT System v2.0</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML', chat_id=chat, bot_token=token)


def notificar_alerta_telegram(alerta, cultivo=None, especie=None):
    """
    Envía una notificación instantánea a Telegram cuando se dispara una alerta.
    """
    cfg = obtener_config_telegram()
    if not cfg.get('notificaciones_activas') or not cfg.get('bot_token') or not cfg.get('chat_id'):
        return {'ok': False, 'motivo': 'Notificaciones desactivadas o sin configurar'}

    # Resolver nombres
    cultivo_obj = cultivo or getattr(alerta, 'cultivo', None)
    cultivo_nombre = cultivo_obj.nombre if cultivo_obj else f'Cultivo #{alerta.cultivo_id}'
    esp_nombre = ''
    if especie:
        esp_nombre = f" ({especie.nombre_comun})"
    elif cultivo_obj and cultivo_obj.especie:
        esp_nombre = f" ({cultivo_obj.especie.nombre_comun})"

    nivel = alerta.nivel.upper() if alerta.nivel else 'ADVERTENCIA'
    icono_nivel = '🚨' if nivel == 'CRITICA' else '⚠️'
    color_titulo = f"<b>{icono_nivel} ALERTA {nivel} - HydroControl</b>"

    fecha = alerta.created_at.strftime('%d/%m/%Y %H:%M:%S') if hasattr(alerta, 'created_at') and alerta.created_at else datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    texto = (
        f"{color_titulo}\n\n"
        f"🌿 <b>Cultivo:</b> {cultivo_nombre}{esp_nombre}\n"
        f"🏷️ <b>Tipo de Evento:</b> <code>{alerta.tipo}</code>\n"
        f"📢 <b>Mensaje:</b> {alerta.mensaje}\n"
        f"🕒 <b>Fecha:</b> {fecha}\n\n"
        "👉 <i>Revisa el panel de control o ajusta la solución hidropónica.</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def notificar_alta_cultivo(cultivo):
    """Notifica por Telegram cuando un nuevo cultivo es dado de alta en el sistema."""
    cfg = obtener_config_telegram()
    if not cfg.get('notificaciones_activas') or not cfg.get('bot_token') or not cfg.get('chat_id'):
        return {'ok': False, 'motivo': 'Telegram no configurado o notificaciones inactivas'}

    esp = cultivo.especie
    esp_nombre = esp.nombre_comun if esp else 'Sin especie especificada'
    cat_icono = '🍄' if (esp and esp.categoria == 'HONGO') else '🌱'
    fecha = cultivo.fecha_siembra.strftime('%d/%m/%Y') if hasattr(cultivo, 'fecha_siembra') and cultivo.fecha_siembra else 'Hoy'

    rangos_txt = ""
    if esp:
        rangos_txt = (
            f"\n🎯 <b>Parámetros objetivo ({esp.nombre_comun}):</b>\n"
            f"• 🧪 pH: {esp.ph_min} - {esp.ph_max}\n"
            f"• ⚡ EC: {esp.ec_min} - {esp.ec_max} mS/cm\n"
            f"• 🌡️ Temp: {esp.temp_min} - {esp.temp_max} °C\n"
            f"• 💧 Humedad: {esp.humedad_min} - {esp.humedad_max} %\n"
            f"• ☀️ Luz: {esp.luz_horas_min} - {esp.luz_horas_max} h/día\n"
            f"• ⏱️ Ciclo estimado: {esp.ciclo_dias or 'N/D'} días\n"
        )

    texto = (
        f"{cat_icono} <b>¡NUEVO CULTIVO DADO DE ALTA!</b>\n\n"
        f"🏷️ <b>Nombre:</b> {cultivo.nombre}\n"
        f"📖 <b>Especie:</b> {esp_nombre}\n"
        f"📍 <b>Ubicación:</b> {cultivo.ubicacion or 'Sin ubicación definida'}\n"
        f"📅 <b>Fecha de Siembra:</b> {fecha}\n"
        f"{rangos_txt}\n"
        "✅ <i>El sistema comenzará a monitorear sus lecturas y te avisará ante cualquier desbalance.</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def notificar_alta_dispositivo(dispositivo):
    """Notifica por Telegram cuando se da de alta un nuevo dispositivo IoT o placa."""
    cfg = obtener_config_telegram()
    if not cfg.get('notificaciones_activas') or not cfg.get('bot_token') or not cfg.get('chat_id'):
        return {'ok': False, 'motivo': 'Telegram no configurado o notificaciones inactivas'}

    cultivo_nombre = dispositivo.cultivo.nombre if dispositivo.cultivo else 'Sin asignar (global)'

    texto = (
        "🔌 <b>¡NUEVO DISPOSITIVO IOT DADO DE ALTA!</b>\n\n"
        f"📟 <b>Nombre:</b> {dispositivo.nombre}\n"
        f"⚙️ <b>Hardware:</b> {dispositivo.tipo_hardware}\n"
        f"🌿 <b>Cultivo Asociado:</b> {cultivo_nombre}\n"
        f"📍 <b>Ubicación:</b> {dispositivo.ubicacion or 'N/A'}\n"
        f"🔑 <b>API Key:</b> <code>{dispositivo.api_key}</code>\n\n"
        "✅ <i>El dispositivo ya puede enviar telemetría a /api/v1/telemetria</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def notificar_alta_especie(especie):
    """Notifica por Telegram cuando se agrega una nueva especie al catálogo botánico."""
    cfg = obtener_config_telegram()
    if not cfg.get('notificaciones_activas') or not cfg.get('bot_token') or not cfg.get('chat_id'):
        return {'ok': False, 'motivo': 'Telegram no configurado o notificaciones inactivas'}

    cat_icono = '🍄' if especie.categoria == 'HONGO' else '🌱'

    texto = (
        f"📚 <b>NUEVA ESPECIE EN CATÁLOGO</b>\n\n"
        f"{cat_icono} <b>{especie.nombre_comun}</b> (<i>{especie.nombre_cientifico or 'N/A'}</i>)\n"
        f"🏷️ <b>Categoría:</b> {especie.categoria}\n"
        f"🧪 <b>pH ideal:</b> {especie.ph_min} - {especie.ph_max}\n"
        f"⚡ <b>EC ideal:</b> {especie.ec_min} - {especie.ec_max} mS/cm\n"
        f"🌡️ <b>Temperatura:</b> {especie.temp_min} - {especie.temp_max} °C\n"
        f"💧 <b>Humedad:</b> {especie.humedad_min} - {especie.humedad_max} %\n"
        f"⏱️ <b>Ciclo:</b> {especie.ciclo_dias or 'N/D'} días\n\n"
        "✅ <i>Ya disponible para seleccionar en nuevos cultivos.</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def enviar_reporte_telemetria_telegram(cultivo_id):
    """
    Genera y envía por Telegram un reporte completo de telemetría, microclima
    y diagnóstico de Machine Learning para un cultivo específico.
    """
    from models.cultivo import Cultivo
    from services import monitoreo, clima, ml_engine

    cultivo = Cultivo.query.get(cultivo_id)
    if not cultivo:
        return {'ok': False, 'error': f'Cultivo ID {cultivo_id} no encontrado'}

    resumen = monitoreo.obtener_resumen_cultivo(cultivo_id)
    clima_actual = clima.obtener_clima_actual()
    diagnostico_ml = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_actual)

    categoria_icono = '🍄' if (cultivo.especie and cultivo.especie.categoria == 'HONGO') else '🌱'
    esp_nombre = cultivo.especie.nombre_comun if cultivo.especie else 'Sin especie'
    esp_cientifico = f" (<i>{cultivo.especie.nombre_cientifico}</i>)" if (cultivo.especie and cultivo.especie.nombre_cientifico) else ""

    # Diagnóstico IA
    score = diagnostico_ml.get('score_salud', 0)
    diag_titulo = diagnostico_ml.get('diagnostico_titulo', 'Evaluando...')
    icono_diag = diagnostico_ml.get('icono', '🩺')
    recom_ia = diagnostico_ml.get('recomendacion_ia', '')

    lineas_sensores = []
    if resumen:
        for tipo, info in resumen.items():
            en_rango_txt = "✓ En rango" if info.get('en_rango') else "✗ Fuera de rango"
            lineas_sensores.append(
                f"• {info['icono']} <b>{info['nombre']}:</b> {info['valor']} {info['unidad']} (<i>{en_rango_txt}</i>)"
            )
    else:
        lineas_sensores.append("• <i>No hay lecturas registradas todavía.</i>")

    texto_sensores = "\n".join(lineas_sensores)

    # Clima exterior
    t_ext = clima_actual.get('temp_externa', 'N/D')
    h_ext = clima_actual.get('humedad_externa', 'N/D')
    clima_desc = clima_actual.get('descripcion', '')
    d_temp = diagnostico_ml.get('delta_temp', 0)
    d_signo = f"+{d_temp}" if d_temp > 0 else f"{d_temp}"

    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')

    texto = (
        f"📊 <b>REPORTE DE TELEMETRÍA - HydroControl</b>\n\n"
        f"{categoria_icono} <b>Cultivo:</b> {cultivo.nombre}\n"
        f"📖 <b>Especie:</b> {esp_nombre}{esp_cientifico}\n"
        f"📍 <b>Ubicación:</b> {cultivo.ubicacion or 'N/A'} | ⏱️ <b>Día:</b> {cultivo.dias_activo} ({cultivo.progreso}% ciclo)\n\n"
        f"🩺 <b>Salud del Cultivo (IA):</b> <b>{score}%</b> {icono_diag} {diag_titulo}\n"
        f"💡 <i>{recom_ia}</i>\n\n"
        f"📡 <b>Lecturas de Sensores:</b>\n"
        f"{texto_sensores}\n\n"
        f"🌦️ <b>Clima Exterior:</b> {t_ext}°C | Humedad: {h_ext}% (ΔT interior-exterior: {d_signo}°C)\n"
        f"☁️ <i>{clima_desc}</i>\n\n"
        f"🕒 <i>Generado: {ahora}</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def enviar_reporte_general_telegram():
    """Envía un resumen ejecutivo de todos los cultivos activos y alertas pendientes."""
    from services import monitoreo, alertas, clima

    stats = monitoreo.obtener_estadisticas_dashboard()
    alertas_recientes = alertas.obtener_alertas(solo_no_leidas=True, limite=5)
    clima_actual = clima.obtener_clima_actual()

    lineas_cultivos = []
    for c in stats.get('cultivos', []):
        cat_ico = '🍄' if (c.get('especie') and c['especie'].get('categoria') == 'HONGO') else '🌱'
        lineas_cultivos.append(
            f"• {cat_ico} <b>{c['nombre']}</b> (ID: {c['id']}) - Día {c['dias_activo']} ({c['progreso']}%)"
        )

    texto_cultivos = "\n".join(lineas_cultivos) if lineas_cultivos else "• <i>No hay cultivos activos actualmente.</i>"

    ahora = datetime.now().strftime('%d/%m/%Y %H:%M')

    texto = (
        f"🌐 <b>RESUMEN GENERAL - HydroControl</b>\n\n"
        f"🌿 <b>Cultivos Activos:</b> {stats.get('total_cultivos', 0)}\n"
        f"⚠️ <b>Alertas Pendientes:</b> {stats.get('total_alertas', 0)} (🚨 Críticas: {stats.get('alertas_criticas', 0)})\n\n"
        f"📋 <b>Mis Cultivos:</b>\n{texto_cultivos}\n\n"
        f"🌦️ <b>Clima Exterior:</b> {clima_actual.get('temp_externa', 'N/D')}°C | {clima_actual.get('humedad_externa', 'N/D')}% ({clima_actual.get('descripcion', '')})\n"
        f"🕒 <i>{ahora}</i>\n\n"
        "💡 <i>Usa /telemetria &lt;id&gt; para ver detalles de un cultivo específico.</i>"
    )

    return enviar_mensaje_telegram(texto, parse_mode='HTML')


def procesar_comando_telegram(texto_comando, chat_id_remitente):
    """
    Procesa un comando entrante desde Telegram (Webhook o Polling) y responde al chat remitente.
    Comandos soportados:
      /start, /help, /ayuda
      /status, /estado
      /cultivos
      /telemetria [id]
      /clima
      /alertas
    """
    texto = (texto_comando or '').strip()
    partes = texto.split()
    comando = partes[0].lower() if partes else ''

    if comando in ('/start', '/help', '/ayuda'):
        respuesta = (
            "🌿 <b>¡Hola! Bienvenido al Bot de Telemetría HydroControl</b> 🤖\n\n"
            "Comandos disponibles:\n"
            "• <code>/status</code> - Estado general del sistema y alertas\n"
            "• <code>/cultivos</code> - Lista de cultivos activos con sus IDs\n"
            "• <code>/telemetria</code> - Telemetría y diagnóstico IA del primer cultivo\n"
            "• <code>/telemetria &lt;id&gt;</code> - Telemetría del cultivo con ID especificado\n"
            "• <code>/clima</code> - Condiciones climáticas y consejo agronómico\n"
            "• <code>/alertas</code> - Alertas pendientes no leídas\n\n"
            f"🆔 <i>Tu Chat ID es:</i> <code>{chat_id_remitente}</code>"
        )
        return enviar_mensaje_telegram(respuesta, chat_id=chat_id_remitente)

    elif comando in ('/status', '/estado'):
        return enviar_reporte_general_telegram()

    elif comando == '/cultivos':
        from models.cultivo import Cultivo
        cultivos = Cultivo.query.filter_by(estado='ACTIVO').all()
        if not cultivos:
            return enviar_mensaje_telegram("ℹ️ No hay cultivos activos en el sistema.", chat_id=chat_id_remitente)
        lineas = ["🌿 <b>Cultivos Activos:</b>"]
        for c in cultivos:
            ico = '🍄' if (c.especie and c.especie.categoria == 'HONGO') else '🌱'
            lineas.append(f"• ID <b>{c.id}</b>: {ico} {c.nombre} (Día {c.dias_activo})")
        lineas.append("\n💡 <i>Escribe /telemetria &lt;ID&gt; para ver sus datos.</i>")
        return enviar_mensaje_telegram("\n".join(lineas), chat_id=chat_id_remitente)

    elif comando == '/telemetria':
        from models.cultivo import Cultivo
        target_id = None
        if len(partes) > 1 and partes[1].isdigit():
            target_id = int(partes[1])
        else:
            primer_cultivo = Cultivo.query.filter_by(estado='ACTIVO').first()
            if primer_cultivo:
                target_id = primer_cultivo.id

        if not target_id:
            return enviar_mensaje_telegram(
                "ℹ️ No se encontró ningún cultivo activo. Agrega uno o indica el ID: <code>/telemetria &lt;id&gt;</code>",
                chat_id=chat_id_remitente
            )
        return enviar_reporte_telemetria_telegram(target_id)

    elif comando == '/clima':
        from services import clima
        c = clima.obtener_clima_actual()
        t = c.get('temp_externa', 'N/D')
        h = c.get('humedad_externa', 'N/D')
        v = c.get('viento_kmh', 'N/D')
        d = c.get('descripcion', 'N/D')
        consejo = c.get('consejo_agronomico', '')

        mensaje = (
            "🌦️ <b>CLIMA EXTERIOR EN TIEMPO REAL</b>\n\n"
            f"🌡️ <b>Temperatura:</b> {t}°C\n"
            f"💧 <b>Humedad:</b> {h}%\n"
            f"💨 <b>Viento:</b> {v} km/h\n"
            f"☁️ <b>Condición:</b> {d}\n\n"
            f"🌬️ <b>Consejo Agronómico:</b>\n<i>{consejo}</i>"
        )
        return enviar_mensaje_telegram(mensaje, chat_id=chat_id_remitente)

    elif comando == '/alertas':
        from services import alertas
        no_leidas = alertas.obtener_alertas(solo_no_leidas=True, limite=8)
        if not no_leidas:
            return enviar_mensaje_telegram(
                "✅ <b>¡Todo en orden!</b> No hay alertas pendientes no leídas en el sistema.",
                chat_id=chat_id_remitente
            )
        lineas = [f"🚨 <b>Alertas Pendientes ({len(no_leidas)}):</b>\n"]
        for a in no_leidas:
            ico = '🚨' if a.nivel == 'CRITICA' else '⚠️'
            c_nom = a.cultivo.nombre if a.cultivo else f"Cultivo #{a.cultivo_id}"
            lineas.append(f"{ico} <b>{c_nom}</b> ({a.tipo}):\n{a.mensaje}")
        return enviar_mensaje_telegram("\n\n".join(lineas), chat_id=chat_id_remitente)

    else:
        return enviar_mensaje_telegram(
            f"❓ Comando no reconocido: <code>{comando}</code>\n"
            "Escribe <code>/help</code> para ver los comandos válidos.",
            chat_id=chat_id_remitente
        )
