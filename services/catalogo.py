"""Servicio de gestión del catálogo de especies."""
import json
import os
from models import db
from models.especie import Especie


def cargar_catalogo_default():
    """Carga las especies predeterminadas si la base de datos está vacía."""
    if Especie.query.count() > 0:
        return
    
    ruta_catalogo = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'data', 'catalogo_default.json'
    )
    
    if not os.path.exists(ruta_catalogo):
        return
    
    with open(ruta_catalogo, 'r', encoding='utf-8') as f:
        datos = json.load(f)
    
    for especie_data in datos.get('especies', []):
        especie = Especie(**especie_data)
        db.session.add(especie)
    
    db.session.commit()


def buscar_especies(termino=None, categoria=None):
    """Busca especies por término o categoría."""
    query = Especie.query
    if categoria:
        query = query.filter_by(categoria=categoria.upper())
    if termino:
        query = query.filter(
            db.or_(
                Especie.nombre_comun.ilike(f'%{termino}%'),
                Especie.nombre_cientifico.ilike(f'%{termino}%')
            )
        )
    return query.order_by(Especie.nombre_comun).all()


def obtener_especie(especie_id):
    """Obtiene una especie por su ID."""
    return Especie.query.get_or_404(especie_id)


def crear_especie(datos):
    """Crea una nueva especie en el catálogo."""
    especie = Especie(
        nombre_comun=datos['nombre_comun'],
        nombre_cientifico=datos.get('nombre_cientifico', ''),
        categoria=datos['categoria'].upper(),
        ph_min=float(datos.get('ph_min', 5.5)),
        ph_max=float(datos.get('ph_max', 6.5)),
        ec_min=float(datos.get('ec_min', 1.0)),
        ec_max=float(datos.get('ec_max', 2.5)),
        temp_min=float(datos.get('temp_min', 18.0)),
        temp_max=float(datos.get('temp_max', 28.0)),
        humedad_min=float(datos.get('humedad_min', 50.0)),
        humedad_max=float(datos.get('humedad_max', 80.0)),
        luz_horas_min=float(datos.get('luz_horas_min', 8.0)),
        luz_horas_max=float(datos.get('luz_horas_max', 16.0)),
        ciclo_dias=int(datos['ciclo_dias']) if datos.get('ciclo_dias') else None,
        descripcion=datos.get('descripcion', ''),
        imagen_url=datos.get('imagen_url', '')
    )
    db.session.add(especie)
    db.session.commit()
    return especie


def eliminar_especie(especie_id):
    """Elimina una especie del catálogo."""
    especie = Especie.query.get_or_404(especie_id)
    db.session.delete(especie)
    db.session.commit()
