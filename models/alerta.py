from datetime import datetime, timezone
from models import db


class Alerta(db.Model):
    """Alerta generada por el sistema de monitoreo."""
    __tablename__ = 'alertas'

    id = db.Column(db.Integer, primary_key=True)
    cultivo_id = db.Column(db.Integer, db.ForeignKey('cultivos.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)  # PH_ALTO, PH_BAJO, EC_ALTA, TEMP_ALTA, etc.
    mensaje = db.Column(db.Text, nullable=False)
    nivel = db.Column(db.String(20), default='ADVERTENCIA')  # INFO, ADVERTENCIA, CRITICA
    leida = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    NIVELES = {
        'INFO': {'color': 'info', 'icono': 'ℹ️'},
        'ADVERTENCIA': {'color': 'warning', 'icono': '⚠️'},
        'CRITICA': {'color': 'danger', 'icono': '🚨'},
    }

    @property
    def nivel_info(self):
        return self.NIVELES.get(self.nivel, self.NIVELES['INFO'])

    def to_dict(self):
        return {
            'id': self.id,
            'cultivo_id': self.cultivo_id,
            'cultivo_nombre': self.cultivo.nombre if self.cultivo else '',
            'tipo': self.tipo,
            'mensaje': self.mensaje,
            'nivel': self.nivel,
            'nivel_color': self.nivel_info['color'],
            'nivel_icono': self.nivel_info['icono'],
            'leida': self.leida,
            'created_at': self.created_at.isoformat()
        }
