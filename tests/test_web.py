from models import db
from models.especie import Especie
from models.cultivo import Cultivo
from models.alerta import Alerta
from models.dispositivo import Dispositivo
from models.lectura_sensor import LecturaSensor


def test_ruta_dashboard(client, cultivo_planta):
    """Prueba la carga del dashboard principal."""
    res = client.get('/')
    assert res.status_code == 200
    assert b'Dashboard' in res.data
    assert b'Cultivos Activos' in res.data


def test_ruta_catalogo_y_filtros(client):
    """Prueba la lista del catálogo y búsqueda."""
    res = client.get('/catalogo')
    assert res.status_code == 200
    assert b'Lechuga' in res.data

    # Filtrar por hongos
    res_hongo = client.get('/catalogo?categoria=HONGO')
    assert res_hongo.status_code == 200
    assert b'HONGO' in res_hongo.data

    # Buscar por texto
    res_busqueda = client.get('/catalogo?buscar=albahaca')
    assert res_busqueda.status_code == 200
    assert b'Albahaca' in res_busqueda.data


def test_ruta_catalogo_agregar_nueva_especie(client):
    """Prueba agregar una nueva especie al catálogo."""
    datos = {
        'nombre_comun': 'Romero Hidropónico',
        'nombre_cientifico': 'Salvia rosmarinus',
        'categoria': 'PLANTA',
        'ph_min': 5.5,
        'ph_max': 6.5,
        'ec_min': 1.0,
        'ec_max': 1.8,
        'temp_min': 16.0,
        'temp_max': 26.0,
        'humedad_min': 45.0,
        'humedad_max': 65.0,
        'luz_horas_min': 12.0,
        'luz_horas_max': 16.0,
        'ciclo_dias': 60,
        'descripcion': 'Arbusto aromático perenne'
    }
    res = client.post('/catalogo/agregar', data=datos, follow_redirects=True)
    assert res.status_code == 200
    assert b'Romero' in res.data


def test_ruta_cultivos_crud(client, app):
    """Prueba el ciclo de vida de un cultivo: agregar, ver, pausar, simular lecturas."""
    with app.app_context():
        esp = Especie.query.first()
        esp_id = esp.id

    # 1. Crear cultivo
    datos_cultivo = {
        'especie_id': esp_id,
        'nombre': 'Mi Cultivo Web',
        'fecha_siembra': '2026-10-01',
        'ubicacion': 'Módulo Web',
        'notas': 'Prueba automatizada'
    }
    res_crear = client.post('/cultivos/agregar', data=datos_cultivo, follow_redirects=True)
    assert res_crear.status_code == 200
    assert b'Mi Cultivo Web' in res_crear.data

    with app.app_context():
        c = Cultivo.query.filter_by(nombre='Mi Cultivo Web').first()
        c_id = c.id

    # 2. Registrar lectura manual
    res_lectura = client.post(f'/cultivos/{c_id}/lectura', data={
        'tipo': 'PH',
        'valor': '6.1'
    }, follow_redirects=True)
    assert res_lectura.status_code == 200

    # 3. Simular lecturas normales
    res_sim = client.post(f'/cultivos/{c_id}/simular', data={'tipo_simulacion': 'normal'}, follow_redirects=True)
    assert res_sim.status_code == 200
    assert b'Simulaci' in res_sim.data

    # 4. Cambiar estado a PAUSADO
    res_estado = client.post(f'/cultivos/{c_id}/estado', data={'estado': 'PAUSADO'}, follow_redirects=True)
    assert res_estado.status_code == 200
    assert b'PAUSADO' in res_estado.data


def test_ruta_alertas_web(client, app, cultivo_planta):
    """Prueba ver alertas y marcarlas como leídas vía formulario web."""
    with app.app_context():
        alerta = Alerta(cultivo_id=cultivo_planta, tipo='PH_BAJO', mensaje='pH crítico 4.0', nivel='CRITICA')
        db.session.add(alerta)
        db.session.commit()
        alerta_id = alerta.id

    # Ver lista de alertas
    res = client.get('/alertas')
    assert res.status_code == 200
    assert b'pH cr' in res.data

    # Marcar leída
    res_leida = client.post(f'/alertas/{alerta_id}/leer', follow_redirects=True)
    assert res_leida.status_code == 200

    # Marcar todas leídas
    res_todas = client.post('/alertas/leer-todas', follow_redirects=True)
    assert res_todas.status_code == 200


def test_ruta_dispositivos_web(client, app, cultivo_planta):
    """Prueba registrar, ver y gestionar dispositivos vía web."""
    # Ver página
    res_pag = client.get('/dispositivos')
    assert res_pag.status_code == 200
    assert b'Dispositivos' in res_pag.data

    # Crear nuevo dispositivo
    res_nuevo = client.post('/dispositivos/nuevo', data={
        'nombre': 'ESP32 Invernadero 2',
        'tipo_hardware': 'ESP32',
        'cultivo_id': str(cultivo_planta),
        'ubicacion': 'Sector Norte'
    }, follow_redirects=True)
    assert res_nuevo.status_code == 200
    assert b'ESP32 Invernadero 2' in res_nuevo.data

    with app.app_context():
        disp = Dispositivo.query.filter_by(nombre='ESP32 Invernadero 2').first()
        disp_id = disp.id

    # Regenerar key
    res_regen = client.post(f'/dispositivos/{disp_id}/regenerar-key', follow_redirects=True)
    assert res_regen.status_code == 200

    # Eliminar dispositivo
    res_elim = client.post(f'/dispositivos/{disp_id}/eliminar', follow_redirects=True)
    assert res_elim.status_code == 200


def test_cultivo_dashboard_ml_y_clima(client, cultivo_planta):
    """Verifica que el dashboard individual del cultivo renderice el score ML y clima."""
    res = client.get(f'/cultivos/{cultivo_planta}')
    assert res.status_code == 200
    assert b'Machine Learning' in res.data or b'Inteligencia Artificial' in res.data
    assert b'Clima Exterior' in res.data
    assert b'Exportar CSV' in res.data


def test_cultivo_exportar_e_importar_csv_web(client, cultivo_planta):
    """Prueba los endpoints web de descarga y subida de archivos CSV."""
    import io

    # 1. Exportar CSV
    res_exp = client.get(f'/cultivos/{cultivo_planta}/exportar.csv')
    assert res_exp.status_code == 200
    assert 'text/csv' in res_exp.content_type
    assert b'timestamp,cultivo_id' in res_exp.data

    # 2. Importar CSV vía POST multipart/form-data
    csv_bytes = b"timestamp,ph,temperatura\n2026-10-19 12:00:00,6.2,22.0\n"
    data = {
        'archivo_csv': (io.BytesIO(csv_bytes), 'prueba.csv')
    }
    res_imp = client.post(
        f'/cultivos/{cultivo_planta}/importar-csv',
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert res_imp.status_code == 200
    assert b'CSV importado' in res_imp.data


def test_cultivo_reentrenar_ml_y_api(client, cultivo_planta):
    """Prueba el reentrenamiento de ML y la consulta JSON del diagnóstico."""
    # Reentrenar
    res_train = client.post(f'/cultivos/{cultivo_planta}/reentrenar-ml', follow_redirects=True)
    assert res_train.status_code == 200

    # API JSON
    res_api = client.get(f'/api/cultivo/{cultivo_planta}/diagnostico-ml')
    assert res_api.status_code == 200
    data = res_api.get_json()
    assert 'score_salud' in data
    assert 'diagnostico_codigo' in data
    assert 'recomendacion_ia' in data


def test_eliminar_cultivo_cascada(client, app, cultivo_planta):
    """Verifica que eliminar un cultivo limpie lecturas, alertas y desvincule dispositivos."""
    with app.app_context():
        # Crear lectura
        lectura = LecturaSensor(cultivo_id=cultivo_planta, tipo='PH', valor=6.0)
        db.session.add(lectura)

        # Crear alerta
        alerta = Alerta(cultivo_id=cultivo_planta, tipo='TEMP_ALTA', mensaje='Temp alta', nivel='ADVERTENCIA')
        db.session.add(alerta)

        # Asociar dispositivo
        disp = Dispositivo(
            nombre='Sensor Raiz',
            tipo_hardware='ESP32',
            api_key=Dispositivo.generar_api_key(),
            cultivo_id=cultivo_planta
        )
        db.session.add(disp)
        db.session.commit()

        disp_id = disp.id

    # Ejecutar eliminación vía POST
    res = client.post(f'/cultivos/{cultivo_planta}/eliminar', follow_redirects=True)
    assert res.status_code == 200
    assert b'eliminado correctamente' in res.data or b'eliminado' in res.data

    with app.app_context():
        # Verificar que el cultivo ya no existe
        assert Cultivo.query.get(cultivo_planta) is None
        # Verificar que lecturas y alertas fueron eliminadas
        assert LecturaSensor.query.filter_by(cultivo_id=cultivo_planta).count() == 0
        assert Alerta.query.filter_by(cultivo_id=cultivo_planta).count() == 0
        # Verificar que el dispositivo se conservó pero se desvinculó (cultivo_id es None)
        disp_actualizado = Dispositivo.query.get(disp_id)
        assert disp_actualizado is not None
        assert disp_actualizado.cultivo_id is None


