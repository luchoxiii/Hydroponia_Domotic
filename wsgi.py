"""
Punto de Entrada WSGI para Servidores de Producción (Waitress, Gunicorn, uWSGI).
================================================================================
Permite levantar HydroControl de forma robusta con múltiples hilos de ejecución,
sin servidor de depuración, con rotación de logs y cabeceras de seguridad.
"""
import os
import sys

# Asegurar compatibilidad de encoding en terminales Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Asegurar que el directorio raíz del proyecto está en el PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from config import ProductionConfig, obtener_config
from app import crear_app

# Instancia de aplicación configurada para producción
app = crear_app(config_class=ProductionConfig)


def iniciar_servidor_produccion():
    """Lanza el servidor WSGI empresarial Waitress con multi-threading."""
    try:
        from waitress import serve
    except ImportError:
        print("[ERROR] Waitress no esta instalado. Ejecuta: pip install waitress")
        sys.exit(1)

    host = app.config.get('HOST', '0.0.0.0')
    port = app.config.get('PORT', 5000)
    threads = app.config.get('WAITRESS_THREADS', 8)

    print("=" * 70)
    print("HYDROCONTROL - SERVIDOR WSGI DE PRODUCCION (WAITRESS)")
    print("=" * 70)
    print(f"Estado: ACTIVO (Modo Produccion Endurecido)")
    print(f"Escuchando en: http://{host}:{port}")
    print(f"Hilos de trabajo concurrentes: {threads}")
    print(f"Seguridad: DEBUG=False, ProxyFix={app.config.get('USE_PROXY_FIX')}")
    print(f"Logging rotativo en: {os.path.join(app.config.get('LOG_DIR', 'logs'), 'hydrocontrol.log')}")
    print(f"Healthcheck: http://{host}:{port}/health")
    print("=" * 70)
    print("Presiona Ctrl+C para detener el servidor de forma segura.\n")

    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        channel_timeout=60,
        cleanup_interval=30
    )


if __name__ == '__main__':
    iniciar_servidor_produccion()

