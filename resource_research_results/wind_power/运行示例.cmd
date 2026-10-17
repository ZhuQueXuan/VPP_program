@echo off
chcp 65001 >nul
set "WIND_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%WIND_PYTHON%" (
  "%WIND_PYTHON%" -B "%~dp0run_example.py"
) else (
  py -3 -B "%~dp0run_example.py"
)
pause
