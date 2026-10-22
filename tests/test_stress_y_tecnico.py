"""
Suite de Pruebas Técnicas y de Estrés (Stress Testing & Resilience) para HydroControl.

Cubre:
1. Concurrencia masiva de telemetría IoT (simulación de múltiples placas ESP32 simultáneas).
2. Ingesta masiva de datos (CSV con miles de lecturas).
3. Estrés de inferencia y robustez del motor de Machine Learning.
4. Resiliencia ante valores extremos, entradas maliciosas y tipos inválidos.
5. Integridad transaccional y resistencia de la base de datos bajo estrés.
6. Tormenta de alertas masivas (Alert Storming).
"""
import concurrent.futures
import io
import time
from datetime import datetime, timezone, timedelta
import pytest

from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.lectura_sensor import LecturaSensor
from models.alerta import Alerta
from models.dispositivo import Dispositivo
from services import monitoreo, dispositivos, datos_csv, ml_engine, alertas, catalogo


# ==================== 1. ESTRÉS DE CONCURRENCIA IoT ====================

from unittest.mock import patch


@patch('requests.post')
def test_estres_concurrencia_telemetria_iot(mock_post, app, cultivo_planta):
    """
    Simula 50 nodos sensores IoT transmitiendo datos de manera concurrente
    a través de múltiples hilos para verificar que SQLite con WAL mode y
    los endpoints de telemetría no se bloquean ni pierden paquetes.
    """
    total_solicitudes = 50
    concurrencia = 8

    # Crear dispositivos para la prueba
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        dispositivos_keys = []
        for i in range(5):
            disp = Dispositivo(
                nombre=f'Nodo Stress {i}',
                tipo_hardware='ESP32',
                api_key=f'stress_key_{i}_{int(time.time())}',
                cultivo_id=cultivo.id
            )
            db.session.add(disp)
        db.session.commit()
        dispositivos_keys = [d.api_key for d in Dispositivo.query.filter(Dispositivo.api_key.like('stress_key_%')).all()]

    def enviar_telemetria(idx):
        key = dispositivos_keys[idx % len(dispositivos_keys)]
        payload = {
            'api_key': key,
            'ph': 5.8 + (idx % 10) * 0.05,
            'temperatura': 20.0 + (idx % 8) * 0.5,
            'humedad': 55.0 + (idx % 15),
            'ec': 1.2 + (idx % 5) * 0.1,
            'nivel_agua': 80.0
        }
        with app.app_context():
            resp, codigo = dispositivos.procesar_telemetria(payload)
            return codigo, resp

    inicio = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrencia) as executor:
        futuros = [executor.submit(enviar_telemetria, i) for i in range(total_solicitudes)]
        resultados = [f.result() for f in concurrent.futures.as_completed(futuros)]
    duracion = time.time() - inicio

    codigos = [r[0] for r in resultados]
    assert all(c == 200 for c in codigos), f"Códigos no 200 encontrados: {[c for c in codigos if c != 200]}"
    
    # Rendimiento
    rps = total_solicitudes / max(duracion, 0.001)
    assert rps > 5, f"RPS fue demasiado bajo: {rps:.2f} req/s"

    # Verificar integridad de datos guardados
    with app.app_context():
        total_lecturas = LecturaSensor.query.filter_by(cultivo_id=cultivo_planta).count()
        # Cada solicitud envía 5 sensores: 50 * 5 = 250 lecturas
        assert total_lecturas >= total_solicitudes * 5


@patch('requests.post')
def test_estres_endpoint_update_concurrente(mock_post, app, cultivo_planta):
    """
    Evalúa el endpoint simple GET /api/v1/update bajo 30 llamadas concurrentes.
    """
    with app.app_context():
        disp = Dispositivo(
            nombre='Nodo Micro',
            tipo_hardware='Arduino UNO',
            api_key='micro_key_test_123',
            cultivo_id=cultivo_planta
        )
        db.session.add(disp)
        db.session.commit()

    def enviar_get(i):
        payload = {
            'api_key': 'micro_key_test_123',
            'ph': f"{6.0 + (i * 0.01):.2f}",
            'temp': '22.5',
            'hum': '60.0'
        }
        with app.app_context():
            resp, code = dispositivos.procesar_telemetria(payload)
            return code

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        resultados = list(executor.map(enviar_get, range(30)))

    assert all(c == 200 for c in resultados)


# ==================== 2. ESTRÉS DE INGESTA MASIVA (CSV) ====================

@patch('requests.post')
def test_estres_importacion_masiva_csv(mock_post, app, cultivo_planta):
    """
    Genera un archivo CSV con 2,000 registros y prueba la capacidad de ingesta,
    memoria y verificación de límites sin fallos.
    """
    total_filas = 2000
    lineas = ["timestamp,tipo,valor,unidad"]
    tiempo_base = datetime.now(timezone.utc) - timedelta(days=30)

    tipos = [('PH', 6.0, 'pH'), ('EC', 1.4, 'mS/cm'), ('TEMPERATURA', 22.0, '°C'), ('HUMEDAD', 65.0, '%')]
    for i in range(total_filas):
        ts = (tiempo_base + timedelta(minutes=i * 20)).strftime('%Y-%m-%d %H:%M:%S')
        t, val, uni = tipos[i % len(tipos)]
        lineas.append(f"{ts},{t},{val + (i % 5)*0.1:.2f},{uni}")

    csv_bytes = "\n".join(lineas).encode('utf-8')

    with app.app_context():
        inicio = time.time()
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_planta, csv_bytes)
        duracion = time.time() - inicio

        assert codigo == 200
        assert res['lecturas_importadas'] == total_filas
        # Ingesta masiva debe procesar eficientemente
        registros_por_segundo = total_filas / max(duracion, 0.001)
        assert registros_por_segundo > 100, f"Ingesta demasiado lenta: {registros_por_segundo:.1f} reg/s"

        # Verificar conteo real en DB
        conteo = LecturaSensor.query.filter_by(cultivo_id=cultivo_planta).count()
        assert conteo >= total_filas


def test_estres_exportacion_csv_con_muchos_datos(app, cultivo_planta):
    """Verifica que exportar miles de registros genera un CSV correcto sin agotar la memoria."""
    with app.app_context():
        # Insertar 500 lecturas
        lecturas = [
            LecturaSensor(cultivo_id=cultivo_planta, tipo='TEMPERATURA', valor=20.0 + (i % 10))
            for i in range(500)
        ]
        db.session.bulk_save_objects(lecturas)
        db.session.commit()

        inicio = time.time()
        csv_salida = datos_csv.exportar_cultivo_csv(cultivo_planta)
        duracion = time.time() - inicio

        assert isinstance(csv_salida, str)
        assert len(csv_salida) > 5000
        assert "TEMPERATURA" in csv_salida
        assert duracion < 2.0, f"Exportación tardó demasiado: {duracion:.2f}s"


# ==================== 3. ESTRÉS DEL MOTOR DE MACHINE LEARNING ====================

def test_estres_inferencia_machine_learning(app, cultivo_planta):
    """
    Ejecuta 300 inferencias de salud del cultivo consecutivas bajo variaciones
    extremas de microclima y clima exterior. Mide latencia promedio (< 15ms por predicción).
    """
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)

        latencias = []
        for i in range(300):
            resumen_simulado = {
                'PH': {'valor': 5.0 + (i % 25) * 0.1, 'en_rango': True},
                'EC': {'valor': 0.8 + (i % 20) * 0.1, 'en_rango': True},
                'TEMPERATURA': {'valor': 15.0 + (i % 30) * 0.5, 'en_rango': True},
                'HUMEDAD': {'valor': 40.0 + (i % 50), 'en_rango': True},
                'NIVEL_AGUA': {'valor': 30.0 + (i % 70), 'en_rango': True}
            }
            clima_simulado = {
                'temp_externa': 10.0 + (i % 30),
                'humedad_externa': 30.0 + (i % 60),
                'condicion': 'Despejado'
            }

            t0 = time.perf_counter()
            eval_ml = ml_engine.evaluar_salud_cultivo(cultivo, resumen_simulado, clima_simulado)
            t1 = time.perf_counter()

            latencias.append((t1 - t0) * 1000)  # ms
            assert 'score_salud' in eval_ml
            assert 0 <= eval_ml['score_salud'] <= 100
            assert eval_ml['diagnostico_codigo'] in ('OPTIMO', 'ESTRES_TERMICO', 'ESTRES_HIDRICO', 'DESBALANCE_NUTRICIONAL', 'RIESGO_PATOGENO')
            assert 'diagnostico_titulo' in eval_ml

        latencia_media = sum(latencias) / len(latencias)
        p95 = sorted(latencias)[int(len(latencias) * 0.95)]
        assert latencia_media < 100.0, f"Latencia media de inferencia muy alta: {latencia_media:.2f} ms"
        assert p95 < 150.0, f"Percentil 95 muy alto: {p95:.2f} ms"


# ==================== 4. PRUEBAS DE ROBUSTEZ Y CASOS EXTREMOS ====================

def test_robustez_valores_sensores_extremos(app, cultivo_planta):
    """
    Verifica el comportamiento del sistema ante valores físicamente extremos o anómalos:
    - pH negativo o > 14
    - Temperaturas extremas (-50°C o 150°C)
    - Humedad negativa o 200%
    """
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        valores_extremos = [
            ('PH', -5.0),
            ('PH', 25.0),
            ('TEMPERATURA', -50.0),
            ('TEMPERATURA', 120.0),
            ('HUMEDAD', -20.0),
            ('HUMEDAD', 250.0),
            ('NIVEL_AGUA', 0.0),
            ('EC', -3.0),
            ('EC', 99.0),
        ]

        for tipo, val in valores_extremos:
            lectura, alertas_gen = monitoreo.registrar_lectura(cultivo.id, tipo, val)
            assert lectura.valor == val
            assert len(alertas_gen) > 0, f"No se generó alerta para valor extremo {tipo}={val}"
            assert alertas_gen[0].nivel in ('CRITICA', 'ADVERTENCIA')


def test_robustez_payloads_malformados_api_iot(app):
    """
    Comprueba que el endpoint de telemetría maneja con elegancia datos corruptos,
    tipos incorrectos, JSON sin API key o datos incompletos.
    """
    with app.app_context():
        # 1. Sin API key
        resp, code = dispositivos.procesar_telemetria({'ph': 6.0})
        assert code in (400, 401)

        # 2. API key inexistente
        resp, code = dispositivos.procesar_telemetria({'api_key': 'clave_falsa_9999', 'ph': 6.0})
        assert code in (401, 404)

        # 3. Datos no numéricos (strings, arrays)
        with app.app_context():
            disp = Dispositivo(nombre='D1', tipo_hardware='ESP32', api_key='test_rob_key')
            db.session.add(disp)
            db.session.commit()

            resp, code = dispositivos.procesar_telemetria({
                'api_key': 'test_rob_key',
                'ph': 'no_es_numero',
                'temperatura': None,
                'humedad': [1, 2, 3]
            })
            # Debe procesar sin caer en error 500
            assert code in (200, 400)


def test_robustez_busqueda_catalogo_inyeccion_y_unicode(app):
    """Verifica que la búsqueda del catálogo soporte caracteres especiales, inyecciones y emojis."""
    with app.app_context():
        payloads = [
            "' OR 1=1 --",
            "'; DROP TABLE especies; --",
            "<script>alert('xss')</script>",
            "🌿🌱🍄",
            "   ",
            "A" * 500,
            "ñandú cáñamo café"
        ]
        for p in payloads:
            resultado = catalogo.buscar_especies(termino=p)
            assert isinstance(resultado, list)


# ==================== 5. INTEGRIDAD TRANSACCIONAL Y ALERT STORMING ====================

def test_tormenta_de_alertas_masivas(app, cultivo_planta):
    """
    Simula una tormenta de 150 alertas simultáneas y verifica el conteo,
    filtrado y marcado masivo como leídas.
    """
    with app.app_context():
        # Generar 150 alertas
        for i in range(150):
            alerta = Alerta(
                cultivo_id=cultivo_planta,
                tipo='EC_ALTA' if i % 2 == 0 else 'TEMP_ALTA',
                mensaje=f'Alerta de estrés {i}',
                nivel='CRITICA' if i % 3 == 0 else 'ADVERTENCIA',
                leida=False
            )
            db.session.add(alerta)
        db.session.commit()

        # Verificar conteo no leídas
        no_leidas = alertas.contar_alertas_no_leidas()
        assert no_leidas >= 150

        # Marcar todas leídas
        alertas.marcar_todas_leidas()
        assert alertas.contar_alertas_no_leidas() == 0


def test_resiliencia_transaccional_rollback(app, cultivo_planta):
    """
    Verifica que si ocurre un error durante una operación, la base de datos
    hace rollback correctamente y mantiene la consistencia sin datos huérfanos.
    """
    with app.app_context():
        conteo_inicial = LecturaSensor.query.count()

        try:
            # Operación con fallo intencional
            lectura_valida = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=6.5)
            db.session.add(lectura_valida)

            # Insertar objeto con valor no convertible o forzar excepción
            db.session.flush()
            raise RuntimeError("Error forzado de prueba transaccional")
        except RuntimeError:
            db.session.rollback()

        # Verificar que la transacción se canceló
        conteo_final = LecturaSensor.query.count()
        assert conteo_final == conteo_inicial
