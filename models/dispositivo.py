import secrets
from datetime import datetime, timezone, timedelta
from models import db


class Dispositivo(db.Model):
    """Dispositivo IoT o microcontrolador conectado al sistema."""
    __tablename__ = 'dispositivos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo_hardware = db.Column(db.String(50), default='ESP32')  # ESP32, ESP8266, Raspberry Pi, Arduino, MicroPython, Otro
    api_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    cultivo_id = db.Column(db.Integer, db.ForeignKey('cultivos.id'), nullable=True)
    ubicacion = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)
    ultimo_contacto = db.Column(db.DateTime, nullable=True)
    ip_origen = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relación opcional con cultivo
    cultivo = db.relationship('Cultivo', backref=db.backref('dispositivos', lazy=True))

    @staticmethod
    def generar_api_key():
        """Genera una clave API segura para el dispositivo."""
        return f"hydro_{secrets.token_hex(16)}"

    @property
    def online(self):
        """Indica si el dispositivo envió datos en los últimos 15 minutos."""
        if not self.ultimo_contacto:
            return False
        # Manejar aware/naive datetimes
        ahora = datetime.now(timezone.utc)
        contacto = self.ultimo_contacto
        if contacto.tzinfo is None:
            contacto = contacto.replace(tzinfo=timezone.utc)
        return (ahora - contacto) < timedelta(minutes=15)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'tipo_hardware': self.tipo_hardware,
            'api_key': self.api_key,
            'cultivo_id': self.cultivo_id,
            'cultivo_nombre': self.cultivo.nombre if self.cultivo else None,
            'ubicacion': self.ubicacion,
            'activo': self.activo,
            'online': self.online,
            'ultimo_contacto': self.ultimo_contacto.isoformat() if self.ultimo_contacto else None,
            'ip_origen': self.ip_origen,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
