/*
  ==============================================================
   HydroControl - Firmware Nodo de Sensores ESP32
  ==============================================================
   Este sketch permite a un ESP32 conectarse a WiFi y enviar
   telemetría periódica al sistema HydroControl.
   
   Sensores soportados comúnmente:
   - Sonda pH (analógica en pin A0 / GPIO 34)
   - Sensor EC / TDS (analógico en GPIO 35)
   - Sensor Temperatura / Humedad DHT22 o SHT30 (GPIO 4)
   - Sonda estanca de temperatura DS18B20 (GPIO 5)
   - Sensor de nivel de agua (analógico o ultrasónico HC-SR04)
*/

#include <WiFi.h>
#include <HTTPClient.h>

// ====== CONFIGURACIÓN DE RED Y SERVIDOR ======
const char* WIFI_SSID     = "TU_RED_WIFI";
const char* WIFI_PASSWORD = "TU_PASSWORD_WIFI";

// Dirección del servidor HydroControl (ej: "http://192.168.1.100:5000/api/v1/telemetria")
const char* SERVER_URL    = "http://192.168.1.100:5000/api/v1/telemetria";

// Tu API Key generada en el panel de HydroControl (/dispositivos)
const char* API_KEY       = "hydro_REEMPLAZAR_CON_TU_KEY";

// Intervalo de envío en milisegundos (ej: 30000 = 30 segundos)
const unsigned long INTERVALO_ENVIO_MS = 30000;
unsigned long ultimoEnvio = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- Iniciando HydroControl ESP32 Node ---");

  // Conectar a WiFi
  Serial.print("Conectando a WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi Conectado!");
    Serial.print("Dirección IP local: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nError: No se pudo conectar a WiFi. Reintentará en el loop.");
  }
}

// Funciones de lectura simuladas o reales
float leerPH() {
  // En producción: leer pin analógico y aplicar curva de calibración
  // int raw = analogRead(34);
  // float voltaje = raw * (3.3 / 4095.0);
  // return 3.5 * voltaje + offset;
  return 6.15; // Valor de ejemplo
}

float leerEC() {
  return 1.35; // mS/cm ejemplo
}

float leerTemperatura() {
  return 22.4; // °C ejemplo
}

float leerHumedad() {
  return 64.0; // % ejemplo
}

float leerNivelAgua() {
  return 85.0; // % tanque
}

void enviarTelemetria() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Reconectando WiFi...");
    WiFi.reconnect();
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  // Leer valores de los sensores
  float ph = leerPH();
  float ec = leerEC();
  float temp = leerTemperatura();
  float hum = leerHumedad();
  float agua = leerNivelAgua();

  // Construir payload JSON
  String payload = "{";
  payload += "\"api_key\":\"" + String(API_KEY) + "\",";
  payload += "\"lecturas\":[";
  payload += "{\"tipo\":\"PH\",\"valor\":" + String(ph, 2) + "},";
  payload += "{\"tipo\":\"EC\",\"valor\":" + String(ec, 2) + "},";
  payload += "{\"tipo\":\"TEMPERATURA\",\"valor\":" + String(temp, 1) + "},";
  payload += "{\"tipo\":\"HUMEDAD\",\"valor\":" + String(hum, 1) + "},";
  payload += "{\"tipo\":\"NIVEL_AGUA\",\"valor\":" + String(agua, 1) + "}";
  payload += "]}";

  Serial.println("Enviando telemetria: " + payload);

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("[HTTP] Codigo: %d | Respuesta: %s\n", httpCode, response.c_str());
  } else {
    Serial.printf("[HTTP] Fallo la peticion. Error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
}

void loop() {
  unsigned long ahora = millis();
  if (ahora - ultimoEnvio >= INTERVALO_ENVIO_MS || ultimoEnvio == 0) {
    ultimoEnvio = ahora;
    enviarTelemetria();
  }
}
