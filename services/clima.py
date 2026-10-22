"""Servicio de integración con clima exterior y análisis agroclimático."""
import time
import requests
from datetime import datetime, timezone

# Caché en memoria para evitar saturar la API externa (válido por 10 minutos)
_CACHE_CLIMA = {
    'datos': None,
    'timestamp': 0
}

# Coordenadas por defecto (ej. Buenos Aires / templado, configurable)
LATITUD_DEFAULT = -34.6037
LONGITUD_DEFAULT = -58.3816
CIUDAD_DEFAULT = "Buenos Aires (Estación Referencia)"


def obtener_clima_actual(lat=LATITUD_DEFAULT, lon=LONGITUD_DEFAULT, forzar=False):
    """
    Obtiene las condiciones meteorológicas exteriores actuales.
    Consulta la API gratuita Open-Meteo (sin API key requerida).
    Si no hay conexión a internet, recurre a un estimador agroclimático resiliente.
    """
    ahora = time.time()
    if not forzar and _CACHE_CLIMA['datos'] and (ahora - _CACHE_CLIMA['timestamp'] < 600):
        return _CACHE_CLIMA['datos']

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,apparent_temperature"
        f"&timezone=auto"
    )

    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            data = r.json().get('current', {})
            temp = float(data.get('temperature_2m', 20.0))
            hum = float(data.get('relative_humidity_2m', 55.0))
            viento = float(data.get('wind_speed_10m', 12.0))
            sensacion = float(data.get('apparent_temperature', temp))
            codigo_clima = data.get('weather_code', 0)

            condicion = interpretar_codigo_clima(codigo_clima)

            clima = {
                'fuente': 'Open-Meteo API',
                'temp_externa': round(temp, 1),
                'humedad_externa': round(hum, 1),
                'sensacion_termica': round(sensacion, 1),
                'viento_kmh': round(viento, 1),
                'condicion': condicion,
                'codigo_wmo': codigo_clima,
                'ciudad': CIUDAD_DEFAULT,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            _CACHE_CLIMA['datos'] = clima
            _CACHE_CLIMA['timestamp'] = ahora
            return clima
    except Exception as e:
        pass

    # Modo fallback si no hay internet o falla la API
    clima_fallback = {
        'fuente': 'Simulador Agroclimático Local',
        'temp_externa': 21.0,
        'humedad_externa': 58.0,
        'sensacion_termica': 21.0,
        'viento_kmh': 10.0,
        'condicion': 'Despejado / Agradable',
        'codigo_wmo': 0,
        'ciudad': CIUDAD_DEFAULT,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    _CACHE_CLIMA['datos'] = clima_fallback
    _CACHE_CLIMA['timestamp'] = ahora
    return clima_fallback


def interpretar_codigo_clima(codigo):
    """Mapea códigos meteorológicos WMO a descripciones legibles."""
    if codigo == 0:
        return "☀️ Cielo Despejado"
    elif codigo in [1, 2, 3]:
        return "⛅ Parcialmente Nublado"
    elif codigo in [45, 48]:
        return "🌫️ Niebla / Bruma"
    elif codigo in [51, 53, 55, 61, 63, 65]:
        return "🌧️ Lluvia Ligera a Moderada"
    elif codigo in [71, 73, 75]:
        return "❄️ Nieve"
    elif codigo in [80, 81, 82]:
        return "🌦️ Chubascos"
    elif codigo in [95, 96, 99]:
        return "⛈️ Tormenta Eléctrica"
    return "🌤️ Variable"


def evaluar_impacto_climatico(temp_interna, hum_interna, temp_externa, hum_externa, categoria='PLANTA'):
    """
    Compara las condiciones del microclima interno versus el clima exterior
    y genera recomendaciones para ventilación, humidificación o calefacción.
    """
    delta_temp = round(temp_interna - temp_externa, 1)
    delta_hum = round(hum_interna - hum_externa, 1)

    consejos = []
    accion_recomendada = "Condiciones estables"

    # Comparaciones de temperatura
    if delta_temp > 5.0 and temp_interna > 25.0:
        consejos.append(
            f"El interior está {delta_temp}°C más caliente que el exterior. "
            f"Abrir ventilación pasiva o activar extractores para enfriar con aire fresco exterior ({temp_externa}°C)."
        )
        accion_recomendada = "Ventilar para enfriar"
    elif delta_temp < -4.0 and temp_interna < 18.0:
        consejos.append(
            f"El exterior está más cálido ({temp_externa}°C) que el interior ({temp_interna}°C). "
            f"La ventilación forzada puede aportar calor natural al cultivo."
        )
        accion_recomendada = "Ventilar para templar"
    elif temp_externa > 30.0 and temp_interna > 26.0:
        consejos.append(
            f"Ola de calor exterior ({temp_externa}°C). No ventilar en horas pico para no calentar la solución; "
            f"utilizar recirculación interna y nebulizadores."
        )
        accion_recomendada = "Aislar y recircular"

    # Comparaciones de humedad
    if categoria == 'HONGO':
        if hum_externa < 45.0 and hum_interna < 80.0:
            consejos.append(
                f"Aire exterior muy seco ({hum_externa}%). Reducir renovación directa de aire "
                f"y aumentar los pulsos del nebulizador ultrasónico para mantener >80% de humedad en los hongos."
            )
            accion_recomendada = "Humidificar intensivo"
        elif hum_externa > 85.0:
            consejos.append(
                f"Ambiente exterior con humedad alta ({hum_externa}%). Favorable para reducir consumo hídrico en hongos."
            )
    else:
        # Plantas
        if hum_interna > 80.0 and hum_externa < 65.0:
            consejos.append(
                f"Exceso de humedad interior ({hum_interna}%). Riesgo de botrytis/hongos en hojas verdes. "
                f"Ventilar con aire exterior seco ({hum_externa}%) para secar el dosel foliar."
            )
            accion_recomendada = "Ventilar para deshumidificar"

    if not consejos:
        consejos.append("El microclima interior y el ambiente exterior están en equilibrio armónico.")

    return {
        'delta_temp': delta_temp,
        'delta_hum': delta_hum,
        'consejos': consejos,
        'accion_recomendada': accion_recomendada
    }
