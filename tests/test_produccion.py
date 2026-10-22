"""
Pruebas de preparación y endurecimiento para Producción (Production-Readiness).
Verifica:
1. Configuración de producción (ProductionConfig, obtener_config).
2. Endpoint de salud /health y /api/health para orquestadores.
3. Inyección de cabeceras de seguridad HTTP (X-Frame-Options, etc.).
4. Compatibilidad con el módulo WSGI (Waitress / Gunicorn).
"""
import os
import pytest
from config import ProductionConfig, DevelopmentConfig, TestingConfig, obtener_config


def test_configuracion_produccion_atributos():
    """Verifica que la configuración de producción desactive depuración y habilite seguridad."""
    assert ProductionConfig.DEBUG is False
    assert ProductionConfig.TESTING is False
    assert ProductionConfig.WAITRESS_THREADS >= 4
    assert ProductionConfig.PORT == 5000


def test_obtener_config_entornos(monkeypatch):
    """Verifica la resolución dinámica de configuración según variables de entorno."""
    monkeypatch.setenv('FLASK_ENV', 'production')
    assert obtener_config() == ProductionConfig

    monkeypatch.setenv('FLASK_ENV', 'development')
    assert obtener_config() == DevelopmentConfig

    monkeypatch.setenv('FLASK_ENV', 'testing')
    assert obtener_config() == TestingConfig


def test_endpoint_healthcheck(client):
    """Verifica que /health y /api/health retornen 200 y métricas de salud del sistema."""
    for ruta in ['/health', '/api/health']:
        res = client.get(ruta)
        assert res.status_code == 200
        data = res.get_json()
        assert data['status'] == 'healthy'
        assert data['database'] == 'ok'
        assert 'machine_learning' in data
        assert 'timestamp' in data
        assert 'instance_id' in data


def test_cabeceras_de_seguridad_http(client):
    """Verifica que todas las respuestas incluyan cabeceras de seguridad estándar."""
    res = client.get('/')
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert res.headers.get('X-XSS-Protection') == '1; mode=block'
    assert res.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert 'HydroControl' in res.headers.get('Server', '')


def test_modulo_wsgi_app_import():
    """Verifica que el entrypoint WSGI importe la aplicación correctamente sin errores."""
    import wsgi
    assert hasattr(wsgi, 'app')
    assert wsgi.app is not None
