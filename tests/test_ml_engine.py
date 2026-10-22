"""Pruebas para el motor de Machine Learning y diagnóstico de salud."""
from models.cultivo import Cultivo
from services import ml_engine, clima


def test_entrenar_y_cargar_modelo_ml():
    """Verifica que el modelo entrene y persista correctamente."""
    pipeline = ml_engine.entrenar_modelo(guardar=False)
    assert pipeline is not None
    assert hasattr(pipeline, 'predict')
    assert hasattr(pipeline, 'predict_proba')


def test_evaluar_salud_cultivo_optimo(app, cultivo_planta):
    """Cultivo con valores equilibrados debe obtener puntaje alto y diagnóstico óptimo."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        resumen = {
            'PH': {'valor': 6.0, 'en_rango': True},
            'EC': {'valor': 1.1, 'en_rango': True},
            'TEMPERATURA': {'valor': 21.0, 'en_rango': True},
            'HUMEDAD': {'valor': 60.0, 'en_rango': True},
            'NIVEL_AGUA': {'valor': 85.0, 'en_rango': True},
            'LUZ': {'valor': 12.0, 'en_rango': True}
        }
        clima_test = {'temp_externa': 20.0, 'humedad_externa': 55.0}

        evaluacion = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_test)

        assert 'score_salud' in evaluacion
        assert evaluacion['score_salud'] >= 70
        assert 'recomendacion_ia' in evaluacion
        assert 'probabilidades' in evaluacion
        assert evaluacion['diagnostico_codigo'] == 'OPTIMO'


def test_evaluar_salud_cultivo_estres_hidrico_o_nutricional(app, cultivo_planta):
    """Cultivo con agua casi vacía y pH alterado debe ser penalizado por la IA."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        resumen = {
            'PH': {'valor': 3.8, 'en_rango': False},
            'EC': {'valor': 4.5, 'en_rango': False},
            'TEMPERATURA': {'valor': 22.0, 'en_rango': True},
            'HUMEDAD': {'valor': 55.0, 'en_rango': True},
            'NIVEL_AGUA': {'valor': 12.0, 'en_rango': False},
            'LUZ': {'valor': 12.0, 'en_rango': True}
        }
        clima_test = {'temp_externa': 21.0, 'humedad_externa': 50.0}

        evaluacion = ml_engine.evaluar_salud_cultivo(cultivo, resumen, clima_test)

        assert evaluacion['score_salud'] < 60
        assert len(evaluacion['factores_criticos']) >= 2


def test_obtener_metricas_modelo_ml():
    """Verifica que el reporte de métricas contenga accuracy, f1, importancias y clases."""
    metricas = ml_engine.obtener_metricas_modelo()
    assert metricas['activo'] is True
    assert 'Random Forest' in metricas['algoritmo']
    assert 80.0 <= metricas['accuracy'] <= 100.0
    assert 80.0 <= metricas['f1_score'] <= 100.0
    assert len(metricas['importancias']) >= 5
    assert 'OPTIMO' in metricas['clases']


def test_simular_prediccion_what_if():
    """Verifica el endpoint/función de simulación interactiva con escenarios."""
    # Escenario óptimo
    res_opt = ml_engine.simular_prediccion({
        'ph': 6.0, 'ec': 1.4, 'temp_in': 22.0, 'hum_in': 60.0,
        'agua': 85.0, 'luz': 12.0, 'temp_ext': 20.0, 'hum_ext': 50.0,
        'es_hongo': 0, 'dias': 15
    })
    assert res_opt['diagnostico_codigo'] == 'OPTIMO'
    assert res_opt['score_salud'] >= 80

    # Escenario de calor extremo
    res_calor = ml_engine.simular_prediccion({
        'ph': 6.0, 'ec': 1.4, 'temp_in': 38.0, 'hum_in': 40.0,
        'agua': 70.0, 'luz': 12.0, 'temp_ext': 36.0, 'hum_ext': 30.0,
        'es_hongo': 0, 'dias': 15
    })
    assert res_calor['score_salud'] < 60
    assert len(res_calor['factores_criticos']) >= 1


def test_estimar_gdd_y_cosecha(app, cultivo_planta):
    """Verifica el cálculo de Growing Degree Days y días restantes para cosecha."""
    with app.app_context():
        cultivo = Cultivo.query.get(cultivo_planta)
        gdd = ml_engine.estimar_gdd_y_cosecha(cultivo, temp_media=22.0)
        assert 'gdd_acumulado' in gdd
        assert 'gdd_objetivo' in gdd
        assert 'dias_estimados_restantes' in gdd
        assert 'estado_maduracion' in gdd
        assert gdd['gdd_objetivo'] > 0


def test_rutas_ml_web(client):
    """Verifica las rutas web del dashboard de ML, re-entrenamiento y APIs."""
    # 1. Dashboard de ML
    res_dash = client.get('/ml')
    assert res_dash.status_code == 200
    assert b'Centro de Inteligencia Artificial' in res_dash.data
    assert b'Random Forest' in res_dash.data

    # 2. Métricas JSON
    res_met = client.get('/api/ml/metricas')
    assert res_met.status_code == 200
    assert res_met.get_json()['activo'] is True

    # 3. Simulador JSON POST
    res_sim = client.post('/api/ml/simular', json={
        'ph': 6.2, 'ec': 1.5, 'temp_in': 21.0, 'hum_in': 65.0,
        'agua': 90.0, 'luz': 12.0, 'temp_ext': 20.0, 'hum_ext': 55.0,
        'es_hongo': 0, 'dias': 20
    })
    assert res_sim.status_code == 200
    assert 'diagnostico_codigo' in res_sim.get_json()

    # 4. Re-entrenar modelo
    res_re = client.post('/ml/reentrenar', follow_redirects=True)
    assert res_re.status_code == 200
    assert b're-entrenado' in res_re.data

