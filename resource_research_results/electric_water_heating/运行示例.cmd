@echo off
chcp 65001 >nul
set "WATER_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%WATER_PYTHON%" (
  "%WATER_PYTHON%" -B "%~dp0run_example.py"
) else (
  py -3 -B "%~dp0run_example.py"
)
pause
