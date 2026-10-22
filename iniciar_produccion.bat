@echo off
title HydroControl - Servidor de Produccion (Waitress WSGI)
color 0A
echo =====================================================================
echo    🌱 HYDROCONTROL - INICIANDO EN MODO PRODUCCION (WAITRESS WSGI)
echo =====================================================================
cd /d "%~dp0"

set FLASK_ENV=production
set ENV=production
set DEBUG=false

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual .venv...
    python -m venv .venv
    echo [2/3] Instalando dependencias de produccion...
    call .venv\Scripts\pip.exe install -r requirements.txt
    call .venv\Scripts\pip.exe install waitress
    echo [3/3] Inicializando base de datos...
    call .venv\Scripts\python.exe seed_demo.py
)

call .venv\Scripts\activate.bat

echo.
echo Verificando dependencias...
python -c "import waitress" 2>nul
if %errorlevel% neq 0 (
    echo Instalando servidor WSGI Waitress...
    pip install waitress
)

echo.
echo Iniciando servidor de produccion multihilo en http://localhost:5000 ...
python wsgi.py
pause
