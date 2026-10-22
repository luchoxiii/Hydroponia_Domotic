"""Pruebas para el servicio de clima exterior e integración agroclimática."""
from services import clima


def test_obtener_clima_actual():
    """Verifica que el servicio devuelva datos meteorológicos estructurados."""
    c = clima.obtener_clima_actual()
    assert isinstance(c, dict)
    assert 'temp_externa' in c
    assert 'humedad_externa' in c
    assert 'condicion' in c
    assert isinstance(c['temp_externa'], (int, float))
    assert isinstance(c['humedad_externa'], (int, float))


def test_evaluar_impacto_climatico_ventilacion():
    """Calcula deltas térmicos y aconseja ventilación si el interior está caliente y el exterior fresco."""
    # Interior 28°C, exterior 18°C -> Delta +10°C (abrir ventilación)
    analisis = clima.evaluar_impacto_climatico(
        temp_interna=28.0,
        hum_interna=60.0,
        temp_externa=18.0,
        hum_externa=50.0,
        categoria='PLANTA'
    )
    assert analisis['delta_temp'] == 10.0
    assert 'Ventilar' in analisis['accion_recomendada'] or any('ventilar' in c.lower() for c in analisis['consejos'])


def test_evaluar_impacto_climatico_hongos_humedad():
    """Advierte sobre humidificación si el ambiente exterior es muy seco para hongos."""
    analisis = clima.evaluar_impacto_climatico(
        temp_interna=20.0,
        hum_interna=65.0,  # Bajo para hongos
        temp_externa=22.0,
        hum_externa=30.0,  # Muy seco afuera
        categoria='HONGO'
    )
    assert any('hongo' in c.lower() or 'humidif' in c.lower() for c in analisis['consejos'])
