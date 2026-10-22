import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))

# Cargar automáticamente variables desde .env si existe (sin dependencias adicionales)
_env_file = os.path.join(BASEDIR, '.env')
if os.path.exists(_env_file):
    try:
        with open(_env_file, 'r', encoding='utf-8') as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith('#') and '=' in _line:
                    _k, _v = _line.split('=', 1)
                    _k = _k.strip()
                    _v = _v.strip().strip('"').strip("'")
                    os.environ.setdefault(_k, _v)
    except Exception:
        pass

class Config:
    """Configuración base para el sistema HydroControl."""
    DEBUG = os.environ.get('DEBUG', 'false').lower() in ('1', 'true', 'yes')
    TESTING = False
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hydroponia-secret-key-2024')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(BASEDIR, "data", "hydroponia.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Intervalo de verificación de alertas (segundos)
    INTERVALO_VERIFICACION = 300

    # Optimización de concurrencia para SQLite (evita bloqueos bajo estrés de IoT)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 30
        }
    }

    # Red y Servidor WSGI en Producción
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 5000))
    USE_PROXY_FIX = os.environ.get('USE_PROXY_FIX', 'false').lower() in ('1', 'true', 'yes')
    WAITRESS_THREADS = int(os.environ.get('WAITRESS_THREADS', 8))
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_DIR = os.path.join(BASEDIR, 'logs')

    # Configuración de Telegram (Telemetría y Alertas)
    # También puede configurarse desde la interfaz web o mediante archivo .env
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    TELEGRAM_NOTIFICACIONES = os.environ.get('TELEGRAM_NOTIFICACIONES', 'true').lower() in ('1', 'true', 'yes')

    # Telemetría privada del desarrollador (OCULTA para el usuario final)
    # Permite al creador monitorear instalaciones, altas y consumo de recursos
    DEV_TELEGRAM_BOT_TOKEN = os.environ.get('DEV_TELEGRAM_BOT_TOKEN', '')
    DEV_TELEGRAM_CHAT_ID = os.environ.get('DEV_TELEGRAM_CHAT_ID', '')
    DEV_TELEMETRIA_ACTIVA = os.environ.get('DEV_TELEMETRIA_ACTIVA', 'true').lower() in ('1', 'true', 'yes')

    # Bitácora Cifrada de Auditoría Forense (AES-256 + HMAC SHA-256)
    BITACORA_SECRET_KEY = os.environ.get('BITACORA_SECRET_KEY', 'hydroponia-audit-ledger-master-key-2024')
    BITACORA_ARCHIVO = os.path.join(BASEDIR, 'data', 'bitacora_cifrada.enc')


class DevelopmentConfig(Config):
    """Configuración para entorno de desarrollo local."""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Configuración optimizada y endurecida para entornos de producción."""
    DEBUG = False
    TESTING = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    USE_PROXY_FIX = os.environ.get('USE_PROXY_FIX', 'true').lower() in ('1', 'true', 'yes')


class TestingConfig(Config):
    """Configuración para ejecución de pruebas unitarias."""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    LOG_LEVEL = 'WARNING'


def obtener_config():
    """Retorna la clase de configuración adecuada según el entorno."""
    entorno = os.environ.get('FLASK_ENV', os.environ.get('ENV', 'production')).lower()
    if entorno in ('development', 'dev'):
        return DevelopmentConfig
    elif entorno in ('testing', 'test'):
        return TestingConfig
    return ProductionConfig


