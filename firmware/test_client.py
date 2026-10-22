"""
HydroControl - Cliente de prueba y simulación para PC o Raspberry Pi
Permite probar la conexión y enviar telemetría en tiempo real.
"""
import sys
import time
import argparse
import random
import requests

def enviar_telemetria(url, api_key, forzar_alerta=False):
    endpoint = f"{url.rstrip('/')}/api/v1/telemetria"
    
    if forzar_alerta:
        # Valores extremos para disparar alertas
        ph = round(random.choice([4.2, 8.5]), 2)
        ec = round(random.choice([0.4, 4.8]), 2)
        temp = round(random.choice([10.5, 36.0]), 1)
        hum = round(random.choice([25.0, 98.0]), 1)
        agua = round(random.uniform(10.0, 25.0), 1)
    else:
        # Valores normales en rango óptimo
        ph = round(random.uniform(5.8, 6.4), 2)
        ec = round(random.uniform(1.1, 1.8), 2)
        temp = round(random.uniform(20.0, 24.5), 1)
        hum = round(random.uniform(55.0, 70.0), 1)
        agua = round(random.uniform(75.0, 95.0), 1)

    payload = {
        "api_key": api_key,
        "ph": ph,
        "ec": ec,
        "temperatura": temp,
        "humedad": hum,
        "nivel_agua": agua,
        "luz": 14.0
    }

    try:
        r = requests.post(endpoint, json=payload, timeout=5)
        print(f"[{r.status_code}] pH={ph} | EC={ec} | Temp={temp}°C | Hum={hum}% | Agua={agua}%")
        data = r.json()
        if data.get('alertas_generadas', 0) > 0:
            print(f"  ⚠️  ¡ALERTA DETECTADA POR EL SERVIDOR! ({data['alertas_generadas']} alertas generadas):")
            for a in data.get('alertas', []):
                print(f"      - [{a['nivel']}] {a['tipo']}: {a['mensaje']}")
        else:
            print(f"  ✓ Datos procesados OK por el servidor.")
        return True
    except Exception as e:
        print(f"❌ Error al conectar con {endpoint}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Cliente IoT para HydroControl")
    parser.add_argument("--url", default="http://localhost:5000", help="URL del servidor HydroControl")
    parser.add_argument("--key", required=True, help="API Key del dispositivo")
    parser.add_argument("--loop", action="store_true", help="Enviar continuamente en bucle")
    parser.add_argument("--intervalo", type=int, default=10, help="Segundos entre envíos (con --loop)")
    parser.add_argument("--alerta", action="store_true", help="Forzar lecturas anómalas para probar alertas")

    args = parser.parse_args()

    # Primero probar ping
    ping_url = f"{args.url.rstrip('/')}/api/v1/ping?api_key={args.key}"
    try:
        res = requests.get(ping_url, timeout=4).json()
        print(f"🟢 Servidor conectado exitosamente. Dispositivo reconocido: '{res.get('dispositivo')}'")
    except Exception as e:
        print(f"⚠️ Aviso: No se pudo hacer ping a {ping_url} ({e}). Intentando enviar igual...")

    if args.loop:
        print(f"Iniciando bucle de envío cada {args.intervalo}s (Ctrl+C para salir)...")
        while True:
            enviar_telemetria(args.url, args.key, forzar_alerta=args.alerta)
            time.sleep(args.intervalo)
    else:
        enviar_telemetria(args.url, args.key, forzar_alerta=args.alerta)

if __name__ == '__main__':
    main()
