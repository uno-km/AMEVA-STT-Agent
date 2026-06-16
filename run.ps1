# AMEVA STT Agent 실행 및 환경 진단 스크립트

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
if ($ScriptPath) { Set-Location -Path $ScriptPath }

$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if ($PSVersionTable.PSVersion.Major -le 5) { chcp 65001 | Out-Null }
$ErrorActionPreference = "Stop"

Write-Host "--- AMEVA STT Agent Environment Setup ---" -ForegroundColor Cyan
Write-Host "Path: $(Get-Location)" -ForegroundColor Gray

# [0] 8500 포트 점유 프로세스 정리
Write-Host "Checking port 8500..." -ForegroundColor Yellow
$proc = Get-NetTCPConnection -LocalPort 8500 -State Listen -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "Killing existing process holding port 8500 (PID: $($proc.OwningProcess))..." -ForegroundColor DarkYellow
    Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
}

# [1] FFmpeg 자율 설치 및 바인딩
$ffmpegPath = "C:\ffmpeg\bin"
if (-not (Test-Path "$ffmpegPath\ffmpeg.exe")) {
    Write-Host "ffmpeg not found. Installing ffmpeg automatically..." -ForegroundColor Yellow
    
    if (Test-Path "C:\ffmpeg\bin") {
        if (-not (Get-Item "C:\ffmpeg\bin" | Where-Object { $_.PSIsContainer })) {
            Remove-Item -Path "C:\ffmpeg\bin" -Force -ErrorAction SilentlyContinue
        }
    }
    
    New-Item -ItemType Directory -Path "C:\ffmpeg" -Force | Out-Null
    New-Item -ItemType Directory -Path "C:\ffmpeg\bin" -Force | Out-Null
    
    $zipPath = "C:\ffmpeg\ffmpeg.zip"
    $downloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    
    try {
        Write-Host "Downloading ffmpeg static essentials zip..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 600
        
        Write-Host "Extracting ffmpeg archive..." -ForegroundColor Yellow
        Expand-Archive -Path $zipPath -DestinationPath "C:\ffmpeg\extracted" -Force
        
        $binFolder = Get-ChildItem -Path "C:\ffmpeg\extracted" -Recurse -Directory -Filter "bin" | Select-Object -First 1
        if ($binFolder) {
            Copy-Item -Path "$($binFolder.FullName)\*" -Destination "C:\ffmpeg\bin" -Recurse -Force
            Write-Host "ffmpeg and ffprobe installed successfully to C:\ffmpeg\bin" -ForegroundColor Green
        } else {
            throw "Failed to find bin folder inside zip"
        }
        
        Remove-Item -Path "C:\ffmpeg\extracted" -Recurse -Force
        Remove-Item -Path $zipPath -Force
    } catch {
        Write-Host "Failed to install ffmpeg automatically: $_" -ForegroundColor Red
        Write-Host "Audio conversion and YouTube audio extraction will not work without ffmpeg." -ForegroundColor Yellow
    }
}

if (Test-Path "$ffmpegPath\ffmpeg.exe") {
    if ($env:PATH -notmatch "C:\\ffmpeg\\bin") {
        $env:PATH += ";C:\ffmpeg\bin"
        [System.Environment]::SetEnvironmentVariable("PATH", $env:PATH, "Process")
    }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notmatch "C:\\ffmpeg\\bin") {
        [Environment]::SetEnvironmentVariable("Path", $userPath + ";C:\ffmpeg\bin", "User")
    }
    Write-Host "ffmpeg mapped in PATH." -ForegroundColor Green
}

# [2] 하드웨어 감지 및 CUDA Toolkit 체크
Write-Host "Scanning Hardware Profile..." -ForegroundColor Yellow
$videoControllers = Get-CimInstance Win32_VideoController
$hasNvidia = $false
$gpuName = ""
foreach ($vc in $videoControllers) {
    if ($vc.Name -match "NVIDIA") { 
        $hasNvidia = $true 
        $gpuName = $vc.Name
    }
}

if ($hasNvidia) {
    Write-Host "NVIDIA GPU detected: $gpuName" -ForegroundColor Green
    
    if (-not $env:CUDA_PATH) {
        Write-Host "CUDA_PATH environment variable missing. Searching registry..." -ForegroundColor Yellow
        $machineCuda = [Environment]::GetEnvironmentVariable('CUDA_PATH', 'Machine')
        if ($machineCuda) {
            [Environment]::SetEnvironmentVariable('CUDA_PATH', $machineCuda, 'Process')
            $env:CUDA_PATH = $machineCuda
            $env:PATH += ";$machineCuda\bin"
            Write-Host "Found CUDA_PATH in Registry: $machineCuda" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] CUDA_PATH registry key not found. CUDA acceleration might fail." -ForegroundColor Yellow
        }
    }
}

# [3] 가상환경(venv) 검증
$EnvDir = ".\venv"
if (-not (Test-Path -Path $EnvDir)) {
    Write-Host "Virtual environment (venv) not found. Creating virtual environment..." -ForegroundColor Yellow
    python -m venv $EnvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
}

# [4] 가상환경 활성화
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
. "$EnvDir\Scripts\Activate.ps1"

# [5] 종속성 설치 및 복구
Write-Host "Upgrading core pip packages..." -ForegroundColor Yellow
& "$EnvDir\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel

$gpuAccelerated = "False"
$hasTorchCuda = $false
if ($hasNvidia) {
    $pytorchCudaCheck = & "$EnvDir\Scripts\python.exe" -W ignore -c "try: import torch; print(torch.cuda.is_available())`nexcept Exception: print('False')" 2>&1
    if ($pytorchCudaCheck -match "True") {
        Write-Host "PyTorch CUDA is already installed and functional." -ForegroundColor Green
        $hasTorchCuda = $true
    } else {
        Write-Host "Installing PyTorch CUDA..." -ForegroundColor Yellow
        & "$EnvDir\Scripts\pip.exe" install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
        $pytorchCudaCheck = & "$EnvDir\Scripts\python.exe" -W ignore -c "try: import torch; print(torch.cuda.is_available())`nexcept Exception: print('False')" 2>&1
        if ($pytorchCudaCheck -match "True") {
            Write-Host "PyTorch CUDA verified." -ForegroundColor Green
            $hasTorchCuda = $true
        }
    }
}

$hasFasterWhisper = $false
try {
    $whisperCheck = & "$EnvDir\Scripts\python.exe" -W ignore -c "try: from faster_whisper import WhisperModel; print('Success')`nexcept Exception: print('Failed')" 2>&1
    if ($whisperCheck -match "Success") {
        $hasFasterWhisper = $true
    }
} catch {}

if (-not $hasFasterWhisper) {
    Write-Host "Installing faster-whisper..." -ForegroundColor Yellow
    & "$EnvDir\Scripts\pip.exe" install faster-whisper --no-cache-dir
    $whisperCheck = & "$EnvDir\Scripts\python.exe" -W ignore -c "try: from faster_whisper import WhisperModel; print('Success')`nexcept Exception: print('Failed')" 2>&1
    if ($whisperCheck -match "Success") {
        $hasFasterWhisper = $true
    }
}

if ($hasFasterWhisper) {
    if ($hasTorchCuda) {
        $cudaTest = & "$EnvDir\Scripts\python.exe" -W ignore -c "
from faster_whisper import WhisperModel
try:
    model = WhisperModel('tiny', device='cuda', compute_type='float16')
    print('Success')
except ValueError:
    try:
        model = WhisperModel('tiny', device='cuda', compute_type='int8')
        print('Success')
    except Exception:
        print('Failed')
except Exception:
    print('Failed')
" 2>&1
        if ($cudaTest -match "Success") {
            Write-Host "CUDA acceleration verified for faster-whisper." -ForegroundColor Green
            $gpuAccelerated = "True"
        } else {
            Write-Host "[WARNING] CUDA validation failed with faster-whisper. Falling back to CPU mode." -ForegroundColor Yellow
            $gpuAccelerated = "False"
        }
    }
}

Write-Host "Installing requirements..." -ForegroundColor Yellow
& "$EnvDir\Scripts\pip.exe" install -r requirements.txt --quiet

# [6] 폴더 생성
$paths = @("C:\ameva\input", "C:\ameva\outputs", "$ScriptPath\db")
foreach ($p in $paths) {
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Force -Path $p | Out-Null
    }
}

# [7] 실행 가동
Write-Host "Launching AMEVA STT Agent..." -ForegroundColor Cyan
$env:AMEVA_GPU_ACCELERATED = "$gpuAccelerated"
$env:AMEVA_GPU_NAME = "$gpuName"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

& "$EnvDir\Scripts\streamlit.exe" run app.py --server.port 8500
