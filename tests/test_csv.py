"""Pruebas para el servicio de importación y exportación de archivos CSV."""
from models import db
from models.lectura_sensor import LecturaSensor
from models.alerta import Alerta
from services import datos_csv


def test_exportar_cultivo_csv(app, cultivo_planta):
    """Verifica que la exportación CSV contenga encabezados válidos y filas."""
    with app.app_context():
        # Registrar una lectura
        l = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=6.2)
        db.session.add(l)
        db.session.commit()

        csv_str = datos_csv.exportar_cultivo_csv(cultivo_planta)
        assert 'timestamp,cultivo_id,cultivo_nombre' in csv_str
        assert 'PH,pH,6.2' in csv_str


def test_importar_csv_formato_ancho(app, cultivo_planta):
    """Importa archivo CSV en formato multivariable (columnas: timestamp, ph, temperatura, ec)."""
    contenido_csv = (
        "timestamp,ph,temperatura,ec,humedad,nivel_agua\n"
        "2026-10-19 10:00:00,6.0,21.5,1.2,60.0,85.0\n"
        "2026-10-19 11:00:00,6.1,22.0,1.3,62.0,84.0\n"
    )
    with app.app_context():
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_planta, contenido_csv)
        assert codigo == 200
        assert res['status'] == 'ok'
        # 2 filas x 5 sensores = 10 lecturas
        assert res['lecturas_importadas'] == 10


def test_importar_csv_formato_largo(app, cultivo_planta):
    """Importa archivo CSV en formato tabular largo (columnas: timestamp, tipo, valor)."""
    contenido_csv = (
        "timestamp,tipo,valor\n"
        "2026-10-19 14:00:00,PH,6.2\n"
        "2026-10-19 14:00:00,TEMPERATURA,23.5\n"
    )
    with app.app_context():
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_planta, contenido_csv)
        assert codigo == 200
        assert res['lecturas_importadas'] == 2


def test_importar_csv_genera_alertas_automaticas(app, cultivo_planta):
    """Verifica que lecturas anómalas importadas por CSV disparen alertas en el sistema."""
    contenido_csv = (
        "timestamp,ph,nivel_agua\n"
        "2026-10-19 15:00:00,3.2,15.0\n"  # pH 3.2 (crítico) y nivel de agua 15% (crítico)
    )
    with app.app_context():
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_planta, contenido_csv)
        assert codigo == 200
        assert res['alertas_generadas'] >= 2
        # Verificar que existen en la BD
        alertas = Alerta.query.filter_by(cultivo_id=cultivo_planta).all()
        assert len(alertas) >= 2
        assert any(a.tipo == 'PH_BAJO' for a in alertas)
        assert any(a.tipo == 'NIVEL_AGUA_CRITICO' for a in alertas)


def test_importar_csv_vacio_o_invalido(app, cultivo_planta):
    """Manejo de errores si el CSV está vacío o corrupto."""
    with app.app_context():
        res, codigo = datos_csv.importar_lecturas_csv(cultivo_planta, "")
        assert codigo == 400
        assert 'error' in res
