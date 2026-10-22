"""Configuración y fixtures para la suite de pruebas de HydroControl."""
import pytest
from datetime import date, timedelta
from app import crear_app
from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.dispositivo import Dispositivo
from services.catalogo import cargar_catalogo_default


from sqlalchemy.pool import StaticPool


class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': StaticPool,
        'connect_args': {
            'check_same_thread': False
        }
    }



@pytest.fixture
def app(tmp_path, monkeypatch):
    """Crea una instancia de la aplicación configurada para pruebas."""
    test_db_path = str(tmp_path / "test_hydro.db")
    test_bitacora = str(tmp_path / "bitacora_test.enc")
    monkeypatch.setattr('services.bitacora._ruta_bitacora', lambda: test_bitacora)

    class CustomTestConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{test_db_path}'
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {
                'timeout': 30
            }
        }

    app = crear_app(config_class=CustomTestConfig)

    with app.app_context():
        with db.engine.connect() as conn:
            conn.execute(db.text("PRAGMA journal_mode=WAL;"))
            conn.commit()
        db.create_all()
        cargar_catalogo_default()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de pruebas HTTP para Flask."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Runner para comandos CLI si aplica."""
    return app.test_cli_runner()


@pytest.fixture
def cultivo_planta(app):
    """Crea un cultivo de prueba de planta (Lechuga)."""
    with app.app_context():
        esp = Especie.query.filter_by(nombre_comun='Lechuga Butterhead').first()
        cultivo = Cultivo(
            especie_id=esp.id,
            nombre='Lechuga Test',
            fecha_siembra=date.today() - timedelta(days=10),
            ubicacion='Canal Test 1',
            estado='ACTIVO'
        )
        db.session.add(cultivo)
        db.session.commit()
        return cultivo.id


@pytest.fixture
def cultivo_hongo(app):
    """Crea un cultivo de prueba de hongo (Seta Ostra)."""
    with app.app_context():
        esp = Especie.query.filter_by(nombre_comun='Seta Ostra').first()
        cultivo = Cultivo(
            especie_id=esp.id,
            nombre='Seta Ostra Test',
            fecha_siembra=date.today() - timedelta(days=5),
            ubicacion='Cámara Test B',
            estado='ACTIVO'
        )
        db.session.add(cultivo)
        db.session.commit()
        return cultivo.id


@pytest.fixture
def dispositivo_prueba(app, cultivo_planta):
    """Crea un dispositivo IoT vinculado al cultivo de prueba."""
    with app.app_context():
        disp = Dispositivo(
            nombre='ESP32 Test',
            tipo_hardware='ESP32',
            api_key='hydro_test_api_key_1234567890',
            cultivo_id=cultivo_planta,
            ubicacion='Invernadero Test'
        )
        db.session.add(disp)
        db.session.commit()
        return disp.id
