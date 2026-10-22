@echo off
echo =====================================================
echo    Iniciando HydroControl - Sistema de Hidroponia
echo =====================================================
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual...
    python -m venv .venv
    call .venv\Scripts\pip install -r requirements.txt
    call .venv\Scripts\python seed_demo.py
)
call .venv\Scripts\activate.bat
echo Abriendo aplicacion en http://localhost:5000
python app.py
pause
