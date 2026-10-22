from datetime import datetime, timezone
from models import db


class LecturaSensor(db.Model):
    """Lectura individual de un sensor asociado a un cultivo."""
    __tablename__ = 'lecturas_sensor'

    id = db.Column(db.Integer, primary_key=True)
    cultivo_id = db.Column(db.Integer, db.ForeignKey('cultivos.id'), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)  # PH, EC, TEMPERATURA, HUMEDAD, NIVEL_AGUA, LUZ
    valor = db.Column(db.Float, nullable=False)
    unidad = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    TIPOS_SENSOR = {
        'PH': {'nombre': 'pH', 'unidad': 'pH', 'icono': '🧪'},
        'EC': {'nombre': 'Conductividad', 'unidad': 'mS/cm', 'icono': '⚡'},
        'TEMPERATURA': {'nombre': 'Temperatura', 'unidad': '°C', 'icono': '🌡️'},
        'HUMEDAD': {'nombre': 'Humedad', 'unidad': '%', 'icono': '💧'},
        'NIVEL_AGUA': {'nombre': 'Nivel de Agua', 'unidad': '%', 'icono': '🌊'},
        'LUZ': {'nombre': 'Luz', 'unidad': 'horas', 'icono': '☀️'},
    }

    @property
    def tipo_info(self):
        return self.TIPOS_SENSOR.get(self.tipo, {'nombre': self.tipo, 'unidad': '', 'icono': '📊'})

    def to_dict(self):
        return {
            'id': self.id,
            'cultivo_id': self.cultivo_id,
            'tipo': self.tipo,
            'tipo_nombre': self.tipo_info['nombre'],
            'valor': self.valor,
            'unidad': self.unidad or self.tipo_info['unidad'],
            'icono': self.tipo_info['icono'],
            'timestamp': self.timestamp.isoformat()
        }
