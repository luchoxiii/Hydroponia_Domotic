# ==============================================================================
# 🌱 HydroControl - Dockerfile de Producción Multiplataforma
# ==============================================================================
FROM python:3.11-slim

# Metadatos
LABEL maintainer="HydroControl Team"
LABEL description="Sistema Integral de Control, IA y Telemetría para Hidroponía"

# Evitar escritura de archivos .pyc y habilitar buffering de stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    ENV=production \
    DEBUG=false \
    PORT=5000 \
    HOST=0.0.0.0

WORKDIR /app

# Instalar dependencias del sistema mínimas para curl y SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copiar manifiesto de dependencias e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir waitress gunicorn

# Copiar código fuente
COPY . .

# Crear directorios para datos persistentes y logs
RUN mkdir -p /app/data /app/logs

# Exponer puerto de producción
EXPOSE 5000

# Sonda de salud integrada para Docker Engine y Kubernetes
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Comando de inicio mediante servidor WSGI de producción
CMD ["python", "wsgi.py"]
