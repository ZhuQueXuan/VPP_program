@echo off
setlocal
set "TASK_PY=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%TASK_PY%" (
  "%TASK_PY%" -X utf8 -B "%~dp0run_example.py"
) else (
  python -X utf8 -B "%~dp0run_example.py"
)
pause
