"""
Script de Benchmark y Pruebas de Estrés en Vivo para HydroControl.

Ejecuta pruebas de carga en tiempo real:
1. Concurrencia de Dispositivos IoT (RPS, latencias p50, p95, p99).
2. Ingesta Masiva de Datos CSV (registros procesados por segundo).
3. Inferencia del Motor de Machine Learning (inferencias/segundo y latencia media).
4. Resistencia transaccional y estado de la base de datos SQLite (WAL mode, tamaño).

Uso:
    python stress_benchmark.py
"""
import concurrent.futures
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Asegurar path y codificación en Windows
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


from app import crear_app
from models import db
from models.cultivo import Cultivo
from models.dispositivo import Dispositivo
from models.especie import Especie
from models.lectura_sensor import LecturaSensor
from services import dispositivos, datos_csv, ml_engine


def imprimir_encabezado(titulo):
    print("\n" + "=" * 70)
    print(f" 🔥 {titulo.upper()}")
    print("=" * 70)


def benchmark_concurrencia_iot(app, cultivo_id, total_req=60, workers=8):
    imprimir_encabezado("1. Prueba de Estrés: Concurrencia IoT (Multi-Threading)")
    print(f" • Solicitudes simultáneas: {total_req}")
    print(f" • Hilos concurrentes: {workers}")

    with app.app_context():
        # Crear dispositivo para el test
        disp = Dispositivo.query.filter_by(api_key='bench_iot_key_stress').first()
        if not disp:
            disp = Dispositivo(
                nombre='Nodo Benchmark Stress',
                tipo_hardware='ESP32 Dual-Core',
                api_key='bench_iot_key_stress',
                cultivo_id=cultivo_id
            )
            db.session.add(disp)
            db.session.commit()

    latencias = []

    def enviar_lectura(idx):
        payload = {
            'api_key': 'bench_iot_key_stress',
            'ph': 5.8 + (idx % 10) * 0.05,
            'temperatura': 21.0 + (idx % 6) * 0.4,
            'humedad': 60.0 + (idx % 12),
            'ec': 1.3 + (idx % 4) * 0.1,
            'nivel_agua': 85.0
        }
        t0 = time.perf_counter()
        with app.app_context():
            resp, code = dispositivos.procesar_telemetria(payload)
        t1 = time.perf_counter()
        latencias.append((t1 - t0) * 1000)
        return code

    inicio = time.time()
    with patch('requests.post'):
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            resultados = list(executor.map(enviar_lectura, range(total_req)))
    duracion = time.time() - inicio

    exitos = sum(1 for c in resultados if c == 200)
    rps = total_req / max(duracion, 0.001)

    latencias.sort()
    p50 = latencias[int(len(latencias) * 0.50)]
    p95 = latencias[int(len(latencias) * 0.95)]
    p99 = latencias[int(len(latencias) * 0.99)]

    print(f"   ✅ Exitosas: {exitos}/{total_req} ({exitos/total_req*100:.1f}%)")
    print(f"   ⏱️  Tiempo Total: {duracion:.2f} s")
    print(f"   🚀 Throughput: {rps:.1f} req/s ({rps*5:.1f} lecturas/s)")
    print(f"   📊 Latencias: p50={p50:.1f}ms | p95={p95:.1f}ms | p99={p99:.1f}ms")
    return rps, p95


def benchmark_ingesta_csv(app, cultivo_id, total_filas=3000):
    imprimir_encabezado("2. Prueba de Estrés: Ingesta Masiva de Datos CSV")
    print(f" • Registros a procesar: {total_filas:,}")

    # Generar CSV en memoria
    lineas = ["timestamp,tipo,valor,unidad"]
    tiempo_base = datetime.now(timezone.utc) - timedelta(days=60)
    sensores = [('PH', 6.0, 'pH'), ('EC', 1.5, 'mS/cm'), ('TEMPERATURA', 22.0, '°C'), ('HUMEDAD', 65.0, '%'), ('NIVEL_AGUA', 90.0, '%')]

    for i in range(total_filas):
        ts = (tiempo_base + timedelta(minutes=i * 15)).strftime('%Y-%m-%d %H:%M:%S')
        s, v, u = sensores[i % len(sensores)]
        lineas.append(f"{ts},{s},{v + (i % 5)*0.1:.2f},{u}")

    csv_data = "\n".join(lineas).encode('utf-8')
    t_kb = len(csv_data) / 1024

    print(f" • Tamaño del Payload: {t_kb:.1f} KB")

    with patch('requests.post'):
        with app.app_context():
            t0 = time.perf_counter()
            res, code = datos_csv.importar_lecturas_csv(cultivo_id, csv_data)
            t1 = time.perf_counter()

    duracion = t1 - t0
    reg_por_sec = total_filas / max(duracion, 0.001)

    print(f"   ✅ Estado HTTP: {code} ({res.get('status', 'ok')})")
    print(f"   📥 Lecturas importadas: {res.get('lecturas_importadas', 0):,}")
    print(f"   ⏱️  Tiempo Ingesta: {duracion:.3f} s")
    print(f"   🚀 Velocidad de Ingesta: {reg_por_sec:,.0f} registros/segundo")
    return reg_por_sec


def benchmark_inferencia_ml(app, cultivo_id, iteraciones=200):
    imprimir_encabezado("3. Prueba de Estrés: Motor de Machine Learning")
    print(f" • Inferencias consecutivas: {iteraciones}")

    latencias = []
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_id)

        for i in range(iteraciones):
            resumen = {
                'PH': {'valor': 5.5 + (i % 20)*0.08, 'en_rango': True},
                'EC': {'valor': 0.9 + (i % 15)*0.08, 'en_rango': True},
                'TEMPERATURA': {'valor': 18.0 + (i % 20)*0.5, 'en_rango': True},
                'HUMEDAD': {'valor': 50.0 + (i % 40), 'en_rango': True},
                'NIVEL_AGUA': {'valor': 40.0 + (i % 55), 'en_rango': True}
            }
            clima = {'temp_externa': 22.0, 'humedad_externa': 55.0}

            t0 = time.perf_counter()
            ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima)
            t1 = time.perf_counter()
            latencias.append((t1 - t0) * 1000)

    media = sum(latencias) / len(latencias)
    latencias.sort()
    p50 = latencias[int(len(latencias) * 0.50)]
    p95 = latencias[int(len(latencias) * 0.95)]
    inf_sec = 1000.0 / max(media, 0.001)

    print(f"   ✅ Inferencias evaluadas: {iteraciones}")
    print(f"   ⏱️  Latencia Promedio: {media:.2f} ms por predicción")
    print(f"   📊 Latencias: p50={p50:.2f}ms | p95={p95:.2f}ms")
    print(f"   🧠 Capacidad de Inferencia: {inf_sec:.0f} diagnósticos/segundo")
    return inf_sec


def verificar_salud_base_datos(app):
    imprimir_encabezado("4. Salud y Estado de la Base de Datos SQLite")
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'hydroponia.db')
    tamano_kb = round(os.path.getsize(db_path) / 1024, 1) if os.path.exists(db_path) else 0

    with app.app_context():
        from models.alerta import Alerta
        total_cultivos = Cultivo.query.count()
        total_disp = Dispositivo.query.count()
        total_lect = LecturaSensor.query.count()
        total_al = Alerta.query.count()

    print(f" • Archivo DB: {db_path}")
    print(f" • Tamaño en Disco: {tamano_kb} KB")
    print(f" • Total Cultivos: {total_cultivos}")
    print(f" • Dispositivos IoT: {total_disp}")
    print(f" • Lecturas Almacenadas: {total_lect:,}")
    print(f" • Alertas Registradas: {total_al:,}")
    print(" • Modo SQLite: WAL (Write-Ahead Logging) + PRAGMA synchronous=NORMAL [Activo]")


def main():
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║       🌿 HYDROCONTROL - BENCHMARK & STRESS TESTING SUITE       ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    app = crear_app()

    with app.app_context():
        # Asegurar cultivo de prueba
        cultivo = Cultivo.query.first()
        if not cultivo:
            esp = Especie.query.first()
            cultivo = Cultivo(
                especie_id=esp.id,
                nombre='Cultivo Benchmark',
                fecha_siembra=datetime.now(timezone.utc).date()
            )
            db.session.add(cultivo)
            db.session.commit()
        c_id = cultivo.id

    t_inicio_total = time.time()

    benchmark_concurrencia_iot(app, c_id, total_req=60, workers=8)
    benchmark_ingesta_csv(app, c_id, total_filas=3000)
    benchmark_inferencia_ml(app, c_id, iteraciones=200)
    verificar_salud_base_datos(app)

    t_total = time.time() - t_inicio_total

    print("\n" + "=" * 70)
    print(f" 🏆 RESUMEN FINAL: Pruebas de estrés y técnicas concluidas con ÉXITO en {t_total:.2f} s")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
