@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto check_python

py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >nul 2>&1
if errorlevel 1 (
    echo Se necesita Python 3.10 o superior con el lanzador py.
    echo Descarguelo desde https://www.python.org/downloads/ y vuelva a intentarlo.
    goto error
)
echo Creando entorno virtual...
py -3 -m venv .venv
if errorlevel 1 goto error

:check_python
set "PYTHON=%~dp0.venv\Scripts\python.exe"
"%PYTHON%" -c "import sys; sys.exit(sys.version_info < (3, 10))"
if errorlevel 1 (
    echo El entorno .venv necesita Python 3.10 o superior.
    goto error
)
"%PYTHON%" -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Python necesita el componente tcl/tk. Instalelo y vuelva a intentarlo.
    goto error
)
"%PYTHON%" -c "import customtkinter, flask, requests" >nul 2>&1
if not errorlevel 1 goto run
echo Instalando dependencias. Se necesita conexion a Internet...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto error

:run
echo Iniciando simulador local y aplicacion...
echo Credenciales predeterminadas: admin / admin123
"%PYTHON%" main.py --local
if errorlevel 1 goto error
exit /b 0

:error
echo No se pudo iniciar la aplicacion. Revise el mensaje anterior.
pause
exit /b 1