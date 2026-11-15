@echo off
cd /d "%~dp0"
set BACKEND=local
echo ==================================================
echo  Plataforma de multas - modo LOCAL (sin internet)
echo ==================================================
echo Se abrira el navegador en unos segundos.
echo Para cerrar la aplicacion, cierra esta ventana negra.
echo.
where python >nul 2>nul
if %errorlevel%==0 (set PY=python) else (set PY=py)
%PY% -m streamlit run app.py
echo.
echo La aplicacion se detuvo. Si hubo un error, tomale una captura.
pause
