$Host.UI.RawUI.WindowTitle = "AMEVA STT Enterprise - Bootstrapper"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "       AMEVA STT Enterprise Initialization Script" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 0. Clean port 8501
Write-Host "[*] Checking and cleaning port 8501..." -ForegroundColor Yellow
$proc = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "[*] Killing existing process holding port 8501 (PID: $($proc.OwningProcess))..." -ForegroundColor DarkYellow
    Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
}
Write-Host "[OK] Port 8501 is clean." -ForegroundColor Green

# 1. Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}
Write-Host "[OK] Python detected." -ForegroundColor Green

# 2. Venv setup
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "[OK] Virtual environment checked." -ForegroundColor Green

# 3. Activate and Install
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
. .venv\Scripts\Activate.ps1

Write-Host "[*] Checking and installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Dependency installation failed." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}
Write-Host "[OK] Dependencies ready." -ForegroundColor Green

# 4. Make directories
$paths = @("C:\ameva\input", "C:\ameva\outputs", "C:\ameva\AMEVA-STT-Agent\db")
foreach ($p in $paths) {
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Force -Path $p | Out-Null
    }
}

# 5. Launch
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "   🚀 Launching AMEVA STT Enterprise Dashboard..." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
streamlit run app.py
