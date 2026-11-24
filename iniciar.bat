@echo off
title UniFlow — Servidor Local
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] Python nao encontrado. Instale o Python 3.11+ em https://www.python.org/downloads/
    pause
    exit /b 1
)

python start.py
pause
