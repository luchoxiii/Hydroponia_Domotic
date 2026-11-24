"""
Pruebas de Internacionalización (i18n) y Soporte Multilingüe (ES, EN, FR, PT) en HydroControl.
"""
import os
from config import BASEDIR
from services import i18n


def test_idiomas_soportados_y_validacion():
    """Verifica que español, inglés, francés y portugués están registrados y validados."""
    for cod in ('es', 'en', 'fr', 'pt'):
        assert cod in i18n.IDIOMAS_SOPORTADOS
        assert i18n.validar_idioma(cod) == cod
        assert i18n.validar_idioma(cod.upper()) == cod

    # Fallback a español ante códigos no soportados o vacíos
    assert i18n.validar_idioma('de') == 'es'
    assert i18n.validar_idioma('') == 'es'
    assert i18n.validar_idioma(None) == 'es'


def test_traduccion_claves_en_4_idiomas():
    """Verifica que las claves de navegación y sistema traducen correctamente en ES, EN, FR y PT."""
    assert i18n.traducir('nav.catalogo', 'es') == 'Catálogo'
    assert i18n.traducir('nav.catalogo', 'en') == 'Catalog'
    assert i18n.traducir('nav.catalogo', 'fr') == 'Catalogue'
    assert i18n.traducir('nav.catalogo', 'pt') == 'Catálogo'

    assert i18n.traducir('nav.cultivos', 'en') == 'Crops'
    assert i18n.traducir('nav.cultivos', 'fr') == 'Cultures'
    assert i18n.traducir('nav.cultivos', 'pt') == 'Cultivos'

    assert i18n.traducir('nav.bitacora', 'en') == 'Audit Log'
    assert i18n.traducir('nav.bitacora', 'fr') == "Journal d'audit"
    assert i18n.traducir('nav.bitacora', 'pt') == 'Registro de Auditoria'


def test_cambio_idioma_ruta_y_cookie(client):
    """Verifica que /idioma/<lang> cambia el idioma de la interfaz y persiste la cookie."""
    # Cambiar a Inglés (en)
    res_en = client.get('/idioma/en', follow_redirects=True)
    assert res_en.status_code == 200
    assert b'lang="en"' in res_en.data
    assert b'Crops' in res_en.data
    assert b'IoT Devices' in res_en.data

    # Cambiar a Francés (fr)
    res_fr = client.get('/idioma/fr', follow_redirects=True)
    assert res_fr.status_code == 200
    assert b'lang="fr"' in res_fr.data
    assert b'Tableau de bord' in res_fr.data
    assert b'Cultures' in res_fr.data

    # Cambiar a Portugués (pt)
    res_pt = client.get('/idioma/pt', follow_redirects=True)
    assert res_pt.status_code == 200
    assert b'lang="pt"' in res_pt.data
    assert b'Painel' in res_pt.data
    assert b'Registro de Auditoria' in res_pt.data


def test_cambio_idioma_por_query_param(client):
    """Verifica que ?lang=<code_idioma> traduce la página inmediatamente."""
    res = client.get('/?lang=fr')
    assert res.status_code == 200
    assert b'lang="fr"' in res.data
    assert b'Appareils IoT' in res.data


def test_api_i18n_json(client):
    """Verifica el endpoint JSON /api/i18n/<lang_code> para los 4 idiomas."""
    for lang in ('es', 'en', 'fr', 'pt'):
        res = client.get(f'/api/i18n/{lang}')
        assert res.status_code == 200
        data = res.get_json()
        assert data['idioma'] == lang
        assert set(data['idiomas_soportados']) == {'es', 'en', 'fr', 'pt'}
        assert 'nav.dashboard' in data['traducciones']


def test_archivos_readme_multilingues_existen():
    """Verifica que existen y tienen contenido los README en Español, Inglés, Francés y Portugués."""
    archivos = ['README.md', 'README.en.md', 'README.fr.md', 'README.pt.md']
    for nombre in archivos:
        ruta = os.path.join(BASEDIR, nombre)
        assert os.path.exists(ruta), f"Falta el archivo {nombre}"
        assert os.path.getsize(ruta) > 2000, f"El archivo {nombre} está incompleto"
