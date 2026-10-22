"""
HydroControl - Cliente MicroPython para ESP32 / Raspberry Pi Pico W
"""
import network
import time
import urequests
import ujson

# ====== CONFIGURACIÓN ======
WIFI_SSID = "TU_WIFI_SSID"
WIFI_PASSWORD = "TU_WIFI_PASSWORD"
SERVER_URL = "http://192.168.1.100:5000/api/v1/telemetria"
API_KEY = "hydro_REEMPLAZAR_CON_TU_KEY"
INTERVALO_SEGUNDOS = 30


def conectar_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print(f"Conectando a {WIFI_SSID}...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        intentos = 0
        while not wlan.isconnected() and intentos < 20:
            time.sleep(0.5)
            intentos += 1
    if wlan.isconnected():
        print("WiFi Conectado! IP:", wlan.ifconfig()[0])
        return True
    print("Error de conexión WiFi")
    return False


def main():
    conectar_wifi()
    while True:
        # Aquí puedes leer tus sensores físicos (ADC, I2C, OneWire)
        datos = {
            "api_key": API_KEY,
            "ph": 6.2,
            "ec": 1.3,
            "temperatura": 22.0,
            "humedad": 65.0,
            "nivel_agua": 82.0
        }

        try:
            res = urequests.post(SERVER_URL, json=datos)
            print(f"[{res.status_code}] Enviado: {res.text}")
            res.close()
        except Exception as e:
            print("Error al enviar telemetría:", e)

        time.sleep(INTERVALO_SEGUNDOS)


if __name__ == '__main__':
    main()
