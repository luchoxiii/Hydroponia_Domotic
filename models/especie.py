from datetime import datetime, timezone
from models import db


class Especie(db.Model):
    """Catálogo de especies de plantas y hongos para hidroponía."""
    __tablename__ = 'especies'

    id = db.Column(db.Integer, primary_key=True)
    nombre_comun = db.Column(db.String(100), nullable=False)
    nombre_cientifico = db.Column(db.String(150))
    categoria = db.Column(db.String(20), nullable=False)  # PLANTA o HONGO
    
    # Rangos ideales
    ph_min = db.Column(db.Float, default=5.5)
    ph_max = db.Column(db.Float, default=6.5)
    ec_min = db.Column(db.Float, default=1.0)  # mS/cm
    ec_max = db.Column(db.Float, default=2.5)
    temp_min = db.Column(db.Float, default=18.0)  # °C
    temp_max = db.Column(db.Float, default=28.0)
    humedad_min = db.Column(db.Float, default=50.0)  # %
    humedad_max = db.Column(db.Float, default=80.0)
    luz_horas_min = db.Column(db.Float, default=8.0)
    luz_horas_max = db.Column(db.Float, default=16.0)
    
    ciclo_dias = db.Column(db.Integer)  # Días estimados del ciclo
    descripcion = db.Column(db.Text)
    imagen_url = db.Column(db.String(500))
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relaciones
    cultivos = db.relationship('Cultivo', backref='especie', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre_comun': self.nombre_comun,
            'nombre_cientifico': self.nombre_cientifico,
            'categoria': self.categoria,
            'ph_min': self.ph_min, 'ph_max': self.ph_max,
            'ec_min': self.ec_min, 'ec_max': self.ec_max,
            'temp_min': self.temp_min, 'temp_max': self.temp_max,
            'humedad_min': self.humedad_min, 'humedad_max': self.humedad_max,
            'luz_horas_min': self.luz_horas_min, 'luz_horas_max': self.luz_horas_max,
            'ciclo_dias': self.ciclo_dias,
            'descripcion': self.descripcion,
            'imagen_url': self.imagen_url
        }
