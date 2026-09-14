@echo off
chcp 65001 >nul
title PC-Phone-Audio
cd /d "%~dp0"
echo [1/2] Checking Python...
python --version || (echo Install Python 3.10+ from python.org, then try again & pause & exit /b 1)
echo [2/2] Installing dependencies...
python -m pip install -r requirements.txt
echo.
echo Starting server...
python server.py
pause
