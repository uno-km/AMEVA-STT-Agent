@echo off
setlocal enabledelayedexpansion

title AMEVA STT Enterprise - Bootstrapper

echo ========================================================
echo        AMEVA STT Enterprise Initialization Script
echo ========================================================
echo.

:: 0. 기존 8501 포트(Streamlit) 프로세스 정리
echo [*] 기존에 구동 중인 Streamlit(8501 포트) 프로세스가 있다면 정리합니다...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)

:: 1. 파이썬 설치 확인
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [에러] 시스템에 Python이 설치되어 있지 않거나 환경 변수(PATH)에 등록되어 있지 않습니다.
    echo Python 3.10 이상을 설치한 후 다시 실행해 주세요.
    pause
    exit /b 1
)
echo [OK] 파이썬 설치 확인 완료.

:: 2. 가상환경 점검 및 생성
if not exist ".venv" (
    echo [*] 가상환경(.venv)이 없습니다. 생성을 시작합니다... (잠시만 기다려주세요)
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [에러] 가상환경 생성 실패!
        pause
        exit /b 1
    )
    echo [OK] 가상환경(.venv) 생성 완료.
) else (
    echo [OK] 기존 가상환경(.venv) 발견.
)

:: 3. 가상환경 활성화
echo [*] 가상환경 활성화 중...
call .venv\Scripts\activate.bat

:: 4. 필수 의존성 패키지 설치 (진행률 표시)
echo.
echo [*] 패키지 무결성 및 최신 버전을 점검합니다...
echo [INFO] 설치 진행률 바가 아래에 표시됩니다.
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [에러] 의존성 패키지 설치 중 문제가 발생했습니다.
    pause
    exit /b 1
)
echo [OK] 의존성 라이브러리 설치/점검 완료.
echo.

:: 5. 필수 디렉터리 구조 자동 생성
if not exist "C:\ameva\input" mkdir "C:\ameva\input"
if not exist "C:\ameva\outputs" mkdir "C:\ameva\outputs"
if not exist "C:\ameva\AMEVA-STT-Agent\db" mkdir "C:\ameva\AMEVA-STT-Agent\db"

:: 6. 앱 구동
echo ========================================================
echo    🚀 모든 준비가 완료되었습니다. 대시보드를 시작합니다.
echo ========================================================
echo.
echo [INFO] 브라우저 창이 자동으로 열리지 않으면 터미널에 표시된 Local URL (예: http://localhost:8501) 을 클릭하세요.
echo.
streamlit run app.py

pause
