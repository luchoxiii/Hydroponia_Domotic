"""Servicio de gestión y conexión de dispositivos IoT y sensores."""
import threading
from datetime import datetime, timezone
from models import db
from models.dispositivo import Dispositivo
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from services.alertas import verificar_lectura
from services.monitoreo import registrar_lectura

_TELEMETRIA_LOCK = threading.Lock()


def listar_dispositivos():
    """Lista todos los dispositivos registrados."""
    return Dispositivo.query.order_by(Dispositivo.created_at.desc()).all()


def obtener_dispositivo(dispositivo_id):
    """Obtiene un dispositivo por su ID."""
    return Dispositivo.query.get(dispositivo_id)


def obtener_por_api_key(api_key):
    """Busca un dispositivo por su API key."""
    if not api_key:
        return None
    return Dispositivo.query.filter_by(api_key=api_key, activo=True).first()


def crear_dispositivo(nombre, tipo_hardware='ESP32', cultivo_id=None, ubicacion=None):
    """Registra un nuevo dispositivo con API key única."""
    api_key = Dispositivo.generar_api_key()
    disp = Dispositivo(
        nombre=nombre.strip(),
        tipo_hardware=tipo_hardware,
        api_key=api_key,
        cultivo_id=cultivo_id if cultivo_id else None,
        ubicacion=ubicacion.strip() if ubicacion else None,
        activo=True
    )
    db.session.add(disp)
    db.session.commit()
    return disp


def eliminar_dispositivo(dispositivo_id):
    """Elimina un dispositivo."""
    disp = Dispositivo.query.get(dispositivo_id)
    if disp:
        db.session.delete(disp)
        db.session.commit()
        return True
    return False


def regenerar_api_key(dispositivo_id):
    """Regenera la API key de un dispositivo."""
    disp = Dispositivo.query.get_or_404(dispositivo_id)
    disp.api_key = Dispositivo.generar_api_key()
    db.session.commit()
    return disp


def procesar_telemetria(datos, ip_origen=None):
    """
    Procesa un payload de telemetría proveniente de un dispositivo IoT.
    Acepta formatos flexibles:
      Formato 1 (bulk con api_key o cultivo_id):
      {
         "api_key": "hydro_...",
         "cultivo_id": 1, # opcional si el dispositivo ya está asignado
         "lecturas": [{"tipo": "PH", "valor": 6.2}, {"tipo": "TEMPERATURA", "valor": 22.5}]
      }

      Formato 2 (simple de lectura única):
      {
         "api_key": "hydro_...",
         "tipo": "PH",
         "valor": 6.2
      }

      Formato 3 (diccionario directo clave-valor):
      {
         "api_key": "hydro_...",
         "ph": 6.2,
         "ec": 1.4,
         "temperatura": 21.5,
         "humedad": 65,
         "nivel_agua": 80,
         "luz": 12
      }
    """
    api_key = datos.get('api_key')
    dispositivo = None

    if api_key:
        dispositivo = obtener_por_api_key(api_key)
        if not dispositivo:
            return {'error': 'API key inválida o dispositivo inactivo'}, 401

    cultivo_id = datos.get('cultivo_id')
    if not cultivo_id and dispositivo and dispositivo.cultivo_id:
        cultivo_id = dispositivo.cultivo_id

    if not cultivo_id:
        return {'error': 'No se especificó cultivo_id y el dispositivo no tiene cultivo pre-asignado'}, 400

    cultivo = Cultivo.query.get(cultivo_id)
    if not cultivo:
        return {'error': f'Cultivo ID {cultivo_id} no encontrado'}, 404

    # Actualizar estado del dispositivo si aplica (se confirma con el commit final)
    if dispositivo:
        dispositivo.ultimo_contacto = datetime.now(timezone.utc)
        if ip_origen:
            dispositivo.ip_origen = ip_origen

    # Mapeo de nombres comunes a tipos de sensor estándar
    MAPA_TIPOS = {
        'ph': 'PH',
        'ec': 'EC',
        'tds': 'EC',
        'temp': 'TEMPERATURA',
        'temperatura': 'TEMPERATURA',
        'hum': 'HUMEDAD',
        'humedad': 'HUMEDAD',
        'agua': 'NIVEL_AGUA',
        'nivel_agua': 'NIVEL_AGUA',
        'water_level': 'NIVEL_AGUA',
        'luz': 'LUZ',
        'light': 'LUZ'
    }

    lecturas_a_guardar = []

    # Caso A: lista de lecturas explícita
    if 'lecturas' in datos and isinstance(datos['lecturas'], list):
        for item in datos['lecturas']:
            tipo = item.get('tipo', '').upper()
            valor = item.get('valor')
            unidad = item.get('unidad')
            if tipo and valor is not None:
                lecturas_a_guardar.append((tipo, valor, unidad))

    # Caso B: lectura única directa tipo/valor
    elif 'tipo' in datos and 'valor' in datos:
        lecturas_a_guardar.append((datos['tipo'].upper(), datos['valor'], datos.get('unidad')))

    # Caso C: claves directas (ej: {"ph": 6.2, "temperatura": 23.4})
    else:
        for clave, valor in datos.items():
            clave_norm = clave.lower().strip()
            if clave_norm in MAPA_TIPOS and valor is not None:
                try:
                    num_val = float(valor)
                    lecturas_a_guardar.append((MAPA_TIPOS[clave_norm], num_val, None))
                except (ValueError, TypeError):
                    continue

    if not lecturas_a_guardar:
        return {'error': 'No se encontraron lecturas válidas en el payload'}, 400

    alertas_totales = []
    alertas_objs = []
    lecturas_creadas = []

    for tipo, valor, unidad in lecturas_a_guardar:
        try:
            lectura = LecturaSensor(
                cultivo_id=cultivo_id,
                tipo=tipo.upper(),
                valor=float(valor),
                unidad=unidad
            )
            db.session.add(lectura)
            lecturas_creadas.append(lectura)

            if cultivo.especie:
                from services.alertas import verificar_lectura
                a_gen = verificar_lectura(lectura, cultivo.especie, auto_commit=False)
                alertas_objs.extend(a_gen)
                for a in a_gen:
                    alertas_totales.append({
                        'id': getattr(a, 'id', None),
                        'tipo': a.tipo,
                        'nivel': a.nivel,
                        'mensaje': a.mensaje
                    })
        except Exception as e:
            db.session.rollback()
            return {'error': f'Error al registrar lectura de {tipo}: {str(e)}'}, 500

    db.session.commit()

    # Despachar notificaciones tras confirmar el commit
    if alertas_objs:
        try:
            from services import notificaciones_usuario
            for alerta in alertas_objs:
                notificaciones_usuario.despachar_alerta(alerta, cultivo=cultivo, especie=cultivo.especie)
        except Exception:
            pass
        try:
            from services import telegram_bot
            for alerta in alertas_objs:
                telegram_bot.notificar_alerta_telegram(alerta, cultivo=cultivo, especie=cultivo.especie)
        except Exception:
            pass

    try:
        from services import bitacora
        bitacora.registrar_evento('TELEMETRIA_IOT', 'IOT', {
            'dispositivo': dispositivo.nombre if dispositivo else 'Directo',
            'cultivo_id': cultivo_id,
            'total_lecturas': len(lecturas_creadas),
            'alertas_generadas': len(alertas_totales)
        })
    except Exception:
        pass

    return {
        'status': 'ok',
        'mensaje': f'Se registraron {len(lecturas_creadas)} lecturas correctamente',
        'cultivo_id': cultivo_id,
        'dispositivo': dispositivo.nombre if dispositivo else 'Directo',
        'total_lecturas': len(lecturas_creadas),
        'alertas_generadas': len(alertas_totales),
        'alertas': alertas_totales
    }, 200


def generar_firmware_esp32(dispositivo, host_url='http://localhost:5000', wifi_ssid='MI_WIFI_RED', wifi_pass='PASSWORD_WIFI'):
    """
    Genera el código C++ (.ino) completo para ESP32 / ESP8266 con las credenciales
    y API Key del dispositivo ya inyectadas para flasheo directo en 1 clic.
    """
    endpoint = f"{host_url.rstrip('/')}/api/v1/telemetria"
    cultivo_info = f"Cultivo ID: {dispositivo.cultivo_id} ({dispositivo.cultivo.nombre})" if (dispositivo.cultivo) else "Cultivo: Asignación dinámica en servidor"

    return f"""/*
 * ====================================================================
 * HydroControl IoT - Firmware para {dispositivo.nombre}
 * Hardware: {dispositivo.tipo_hardware}
 * {cultivo_info}
 * Generado automáticamente por HydroControl
 * ====================================================================
 * INSTRUCCIONES RÁPIDAS:
 * 1. Abre este archivo en Arduino IDE.
 * 2. Selecciona tu placa (ej: ESP32 Dev Module) y el puerto COM.
 * 3. Haz clic en "Subir" (Flecha). ¡Listo! Comenzará a enviar datos.
 */

#include <WiFi.h>
#include <HTTPClient.h>

// Credenciales WiFi pre-rellenadas
const char* ssid = "{wifi_ssid}";
const char* password = "{wifi_pass}";

// Endpoint y Clave de Autenticación de HydroControl
const char* serverUrl = "{endpoint}";
const char* apiKey = "{dispositivo.api_key}";

// Pines de Sensores (Ajusta según tu conexión física)
const int PIN_SENSOR_PH = 34;      // Entrada analógica pH
const int PIN_SENSOR_TEMP = 35;    // Entrada analógica Temperatura
const int PIN_NIVEL_AGUA = 32;     // Entrada analógica Nivel de Agua
const int INTERVALO_ENVIO_MS = 30000; // Enviar telemetría cada 30 segundos

void setup() {{
  Serial.begin(115200);
  delay(1000);
  Serial.println("\\nIniciando {dispositivo.nombre} - HydroControl...");

  WiFi.begin(ssid, password);
  Serial.print("Conectando a red WiFi ");
  while (WiFi.status() != WL_CONNECTED) {{
    delay(500);
    Serial.print(".");
  }}
  Serial.println("\\nWiFi Conectado!");
  Serial.print("Dirección IP asignada: ");
  Serial.println(WiFi.localIP());
}}

float leerSensorPH() {{
  int raw = analogRead(PIN_SENSOR_PH);
  // Calibración típica analógica (0 - 4095 a pH 0 - 14)
  return 3.3 + (raw / 4095.0) * 4.0;
}}

float leerSensorTemp() {{
  int raw = analogRead(PIN_SENSOR_TEMP);
  // Ejemplo termistor NTC o DS18B20
  return 18.0 + (raw / 4095.0) * 12.0;
}}

float leerSensorAgua() {{
  int raw = analogRead(PIN_NIVEL_AGUA);
  return (raw / 4095.0) * 100.0;
}}

void loop() {{
  if (WiFi.status() == WL_CONNECTED) {{
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");

    // Adquisición de muestras
    float ph = leerSensorPH();
    float temp = leerSensorTemp();
    float agua = leerSensorAgua();
    float ec = 1.45; // Valor calibrado sonda EC

    // Construcción del payload JSON
    String jsonPayload = "{{";
    jsonPayload += "\\"api_key\\":\\"" + String(apiKey) + "\\",";
    jsonPayload += "\\"ph\\":" + String(ph, 2) + ",";
    jsonPayload += "\\"temperatura\\":" + String(temp, 1) + ",";
    jsonPayload += "\\"ec\\":" + String(ec, 2) + ",";
    jsonPayload += "\\"nivel_agua\\":" + String(agua, 1);
    jsonPayload += "}}";

    Serial.println("Enviando telemetría a HydroControl...");
    int httpResponseCode = http.POST(jsonPayload);

    if (httpResponseCode > 0) {{
      String response = http.getString();
      Serial.printf("Respuesta [%d]: %s\\n", httpResponseCode, response.c_str());
    }} else {{
      Serial.printf("Error de envío HTTP: %s\\n", http.errorToString(httpResponseCode).c_str());
    }}
    http.end();
  }} else {{
    Serial.println("WiFi desconectado. Intentando reconectar...");
    WiFi.reconnect();
  }}

  delay(INTERVALO_ENVIO_MS);
}}
"""


def crear_o_obtener_dispositivo_virtual(cultivo_id=None):
    """Obtiene o crea un dispositivo virtual para pruebas instantáneas sin hardware."""
    nombre = "Simulador Virtual IoT"
    disp = Dispositivo.query.filter_by(nombre=nombre).first()
    if not disp:
        disp = crear_dispositivo(
            nombre=nombre,
            tipo_hardware="Simulador Virtual",
            cultivo_id=cultivo_id,
            ubicacion="Software Local"
        )
    elif cultivo_id and disp.cultivo_id != cultivo_id:
        disp.cultivo_id = cultivo_id
        db.session.commit()
    return disp


def simular_envio_telemetria(dispositivo_id=None, cultivo_id=None, modo='normal'):
    """Genera y procesa una lectura simulada realista para pruebas de un clic."""
    import random
    if dispositivo_id:
        disp = obtener_dispositivo(dispositivo_id)
    else:
        disp = crear_o_obtener_dispositivo_virtual(cultivo_id=cultivo_id)

    target_cultivo_id = cultivo_id or (disp.cultivo_id if disp else None)
    if not target_cultivo_id:
        cultivo = Cultivo.query.filter_by(estado='ACTIVO').first()
        target_cultivo_id = cultivo.id if cultivo else 1

    cultivo = Cultivo.query.get(target_cultivo_id)
    esp = cultivo.especie if cultivo else None

    # Generar lecturas coherentes con la especie
    if modo == 'anomalia':
        ph = 4.2
        ec = 3.8
        temp = 34.5
        hum = 30.0
        agua = 15.0
    else:
        if esp:
            ph = round(random.uniform(esp.ph_min, esp.ph_max), 2)
            ec = round(random.uniform(esp.ec_min, esp.ec_max), 2)
            temp = round(random.uniform(esp.temp_min, esp.temp_max), 1)
            hum = round(random.uniform(esp.humedad_min, esp.humedad_max), 1)
        else:
            ph = round(random.uniform(5.8, 6.4), 2)
            ec = round(random.uniform(1.2, 1.8), 2)
            temp = round(random.uniform(20.0, 24.0), 1)
            hum = round(random.uniform(55.0, 70.0), 1)
        agua = round(random.uniform(75.0, 95.0), 1)

    payload = {
        'api_key': disp.api_key if disp else None,
        'cultivo_id': target_cultivo_id,
        'ph': ph,
        'ec': ec,
        'temperatura': temp,
        'humedad': hum,
        'nivel_agua': agua,
        'luz': 12.0
    }

    resultado, codigo = procesar_telemetria(payload, ip_origen="127.0.0.1 (Simulador)")
    return resultado, codigo, payload


