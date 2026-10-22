#!/usr/bin/env bash
# =====================================================================
#    🌱 HYDROCONTROL - INICIANDO EN MODO PRODUCCION (LINUX / RASPBERRY PI)
# =====================================================================
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

export FLASK_ENV=production
export ENV=production
export DEBUG=false

if [ ! -d ".venv" ]; then
    echo "[1/3] Creando entorno virtual..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    echo "[2/3] Instalando dependencias de producción..."
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install waitress gunicorn
    echo "[3/3] Inicializando base de datos..."
    .venv/bin/python seed_demo.py
fi

source .venv/bin/activate

echo "🚀 Iniciando servidor de producción WSGI..."
python wsgi.py
