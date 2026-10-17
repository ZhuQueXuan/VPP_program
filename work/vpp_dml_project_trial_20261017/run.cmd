@echo off
chcp 65001 >nul
"%~dp0..\vpp_dml_review_20261017\env\Scripts\python.exe" -X utf8 "%~dp0run_experiment.py"
echo.
pause
