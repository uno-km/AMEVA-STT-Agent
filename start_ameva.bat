@echo off
title AMEVA STT Enterprise - Bootstrapper

echo ========================================================
echo        AMEVA STT Enterprise Initialization Script
echo ========================================================
echo.

:: 0. Clean port 8501 if listening
echo [*] Cleaning existing Streamlit process on port 8501...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ and try again.
    pause
    exit /b 1
)
echo [OK] Python detected.

:: 2. Setup Venv
if not exist ".venv" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
)
echo [OK] Virtual environment checked.

:: 3. Activate Venv and Install
echo [*] Activating virtual environment and checking dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)
echo [OK] Dependencies ready.
echo.

:: 4. Make dirs
if not exist "C:\ameva\input" mkdir "C:\ameva\input"
if not exist "C:\ameva\outputs" mkdir "C:\ameva\outputs"
if not exist "C:\ameva\AMEVA-STT-Agent\db" mkdir "C:\ameva\AMEVA-STT-Agent\db"

:: 5. Launch
echo ========================================================
echo    🚀 Launching AMEVA STT Enterprise Dashboard...
echo ========================================================
streamlit run app.py

pause
