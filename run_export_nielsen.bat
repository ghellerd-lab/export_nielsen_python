@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "SCRIPT_DIR=%~dp0."
set "PYTHON=C:\Users\Daniel.GHELLER\AppData\Local\Programs\Python\Python312\python.exe"
set "RUN_LOG=%~dp0run_export_nielsen_output.log"

if not exist "%PYTHON%" (
  echo Nu gasesc Python: "%PYTHON%"
  pause
  exit /b 1
)

if "%~1"=="" (
  "%PYTHON%" -u "%~dp0export_nielsen.py" --properties "%~dp0jobExportNielsen.properties" --base-dir "%SCRIPT_DIR%"
  set "EXIT_CODE=!ERRORLEVEL!"
) else (
  "%PYTHON%" -u "%~dp0export_nielsen.py" %*
  set "EXIT_CODE=!ERRORLEVEL!"
)

echo.
echo Exit code: !EXIT_CODE!
pause
exit /b !EXIT_CODE!
