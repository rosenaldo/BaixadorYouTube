@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%~dp0baixador.py"
  if not errorlevel 1 goto :eof
)
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0baixador.py"
  goto :eof
)
echo.
echo Python nao foi encontrado neste computador.
echo Instale Python 3 pelo site oficial https://www.python.org/downloads/windows/
echo Durante a instalacao, marque "Add python.exe to PATH".
echo Depois execute INICIAR.bat novamente.
echo.
pause
