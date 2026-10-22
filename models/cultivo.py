from datetime import datetime, timezone
from models import db


class Cultivo(db.Model):
    """Instancia activa de un cultivo en el sistema hidropónico."""
    __tablename__ = 'cultivos'

    id = db.Column(db.Integer, primary_key=True)
    especie_id = db.Column(db.Integer, db.ForeignKey('especies.id'), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    fecha_siembra = db.Column(db.Date, nullable=False)
    ubicacion = db.Column(db.String(100))  # Ej: "Canal A - Posición 3"
    estado = db.Column(db.String(20), default='ACTIVO')  # ACTIVO, PAUSADO, COSECHADO, ELIMINADO
    notas = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relaciones con eliminación en cascada
    lecturas = db.relationship('LecturaSensor', backref='cultivo', lazy=True, cascade='all, delete-orphan', order_by='LecturaSensor.timestamp.desc()')
    alertas = db.relationship('Alerta', backref='cultivo', lazy=True, cascade='all, delete-orphan', order_by='Alerta.created_at.desc()')

    @property
    def dias_activo(self):
        from datetime import date
        return (date.today() - self.fecha_siembra).days

    @property
    def progreso(self):
        if self.especie and self.especie.ciclo_dias and self.especie.ciclo_dias > 0:
            return min(100, int((self.dias_activo / self.especie.ciclo_dias) * 100))
        return 0

    @property
    def alertas_no_leidas(self):
        return len([a for a in self.alertas if not a.leida])

    def ultima_lectura(self, tipo):
        for lectura in self.lecturas:
            if lectura.tipo == tipo:
                return lectura
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'especie': self.especie.to_dict() if self.especie else None,
            'fecha_siembra': self.fecha_siembra.isoformat(),
            'ubicacion': self.ubicacion,
            'estado': self.estado,
            'dias_activo': self.dias_activo,
            'progreso': self.progreso,
            'alertas_no_leidas': self.alertas_no_leidas,
            'notas': self.notas
        }
