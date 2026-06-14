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

# 0-1. ffmpeg 자율 설치 및 바인딩
$ffmpegPath = "C:\ffmpeg\bin"
if (-not (Test-Path "$ffmpegPath\ffmpeg.exe")) {
    Write-Host "[*] ffmpeg not found. Installing ffmpeg automatically..." -ForegroundColor Yellow
    
    # 기존에 파일 형식으로 잘못 복사된 bin 파일 강제 제거
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
        Write-Host "[*] Downloading ffmpeg static essentials zip..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 600
        
        Write-Host "[*] Extracting ffmpeg archive..." -ForegroundColor Yellow
        Expand-Archive -Path $zipPath -DestinationPath "C:\ffmpeg\extracted" -Force
        
        # 압축해제된 하위 폴더에서 bin 내용 찾아 복사
        $binFolder = Get-ChildItem -Path "C:\ffmpeg\extracted" -Recurse -Directory -Filter "bin" | Select-Object -First 1
        if ($binFolder) {
            Copy-Item -Path "$($binFolder.FullName)\*" -Destination "C:\ffmpeg\bin" -Recurse -Force
            Write-Host "[OK] ffmpeg and ffprobe installed successfully to C:\ffmpeg\bin" -ForegroundColor Green
        } else {
            throw "Failed to find bin folder inside zip"
        }
        
        # 임시 파일 정리
        Remove-Item -Path "C:\ffmpeg\extracted" -Recurse -Force
        Remove-Item -Path $zipPath -Force
    } catch {
        Write-Host "[ERROR] Failed to install ffmpeg automatically: $_" -ForegroundColor Red
        Write-Host "[WARN] Audio conversion and YouTube audio extraction will not work without ffmpeg." -ForegroundColor Yellow
    }
}

# ffmpeg PATH 임시 등록
if (Test-Path "$ffmpegPath\ffmpeg.exe") {
    if ($env:PATH -notmatch "C:\\ffmpeg\\bin") {
        $env:PATH += ";C:\ffmpeg\bin"
        [System.Environment]::SetEnvironmentVariable("PATH", $env:PATH, "Process")
    }
    # 사용자 PATH 레지스트리에도 등록 (재부팅 시 자동 유지)
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notmatch "C:\\ffmpeg\\bin") {
        [Environment]::SetEnvironmentVariable("Path", $userPath + ";C:\ffmpeg\bin", "User")
    }
    Write-Host "[OK] ffmpeg and ffprobe mapped in PATH." -ForegroundColor Green
}

# 1. Hardware Profiling & GPU Detection
Write-Host "[*] Scanning Hardware Profile..." -ForegroundColor Yellow
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
    Write-Host "[OK] NVIDIA GPU detected: $gpuName" -ForegroundColor Green
    
    # CUDA_PATH 임시 바인딩 보정
    if (-not $env:CUDA_PATH) {
        Write-Host "[*] CUDA_PATH environment variable missing. Searching registry..." -ForegroundColor Yellow
        $machineCuda = [Environment]::GetEnvironmentVariable('CUDA_PATH', 'Machine')
        if ($machineCuda) {
            [Environment]::SetEnvironmentVariable('CUDA_PATH', $machineCuda, 'Process')
            $env:CUDA_PATH = $machineCuda
            $env:PATH += ";$machineCuda\bin"
            Write-Host "[OK] Found CUDA_PATH in Registry: $machineCuda (Loaded temporarily)" -ForegroundColor Green
        } else {
            Write-Host "[WARN] CUDA_PATH registry key not found. CUDA acceleration might fail." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[OK] CUDA_PATH is active: $env:CUDA_PATH" -ForegroundColor Green
    }
} else {
    Write-Host "[*] No NVIDIA GPU detected. Targets set to CPU modes." -ForegroundColor Yellow
}

# 2. Check Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit
}
Write-Host "[OK] Python detected." -ForegroundColor Green

# 3. Venv setup
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}
Write-Host "[OK] Virtual environment checked." -ForegroundColor Green

# 4. Activate virtual environment
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
. .venv\Scripts\Activate.ps1

# 5. Dependency installation & Self-Healing Acceleration Setup
Write-Host "[*] Installing pip-tools and upgrading core packages..." -ForegroundColor Yellow
python -m pip install --upgrade pip setuptools wheel

$gpuAccelerated = "False"

# 5.1 PyTorch CUDA 설치 및 검증 (이미 최적의 버전이 있고 정상 작동하면 Skip)
$hasTorchCuda = $false
if ($hasNvidia) {
    Write-Host "[*] Checking if PyTorch CUDA is already installed..." -ForegroundColor Yellow
    $pytorchCudaCheck = python -c "import torch; print(torch.cuda.is_available())" 2>$null
    if ($pytorchCudaCheck -match "True") {
        Write-Host "[OK] PyTorch CUDA is already installed and functional." -ForegroundColor Green
        $hasTorchCuda = $true
    } else {
        Write-Host "[*] PyTorch CUDA missing or inactive. Installing..." -ForegroundColor Yellow
        pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 --no-cache-dir
        $pytorchCudaCheck = python -c "import torch; print(torch.cuda.is_available())" 2>$null
        if ($pytorchCudaCheck -match "True") {
            Write-Host "[OK] PyTorch CUDA installation and verification passed." -ForegroundColor Green
            $hasTorchCuda = $true
        }
    }
}

# 5.2 faster-whisper 설치 및 검증
$hasFasterWhisper = $false
try {
    $whisperCheck = python -c "from faster_whisper import WhisperModel; print('Success')" 2>$null
    if ($whisperCheck -match "Success") {
        Write-Host "[OK] faster-whisper is already installed and verified." -ForegroundColor Green
        $hasFasterWhisper = $true
    }
} catch {}

if (-not $hasFasterWhisper) {
    Write-Host "[*] Installing faster-whisper..." -ForegroundColor Yellow
    pip install faster-whisper --no-cache-dir
    $whisperCheck = python -c "from faster_whisper import WhisperModel; print('Success')" 2>$null
    if ($whisperCheck -match "Success") {
        Write-Host "[OK] faster-whisper installed and verified." -ForegroundColor Green
        $hasFasterWhisper = $true
    }
}

if ($hasFasterWhisper) {
    if ($hasTorchCuda) {
        Write-Host "[*] Verifying CUDA GPU acceleration with faster-whisper..." -ForegroundColor Yellow
        $cudaTest = python -c "
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
" 2>$null
        if ($cudaTest -match "Success") {
            Write-Host "[OK] CUDA acceleration successfully verified for faster-whisper!" -ForegroundColor Green
            $gpuAccelerated = "True"
        } else {
            Write-Host "[WARN] CUDA validation failed with faster-whisper. Falling back to CPU mode." -ForegroundColor DarkYellow
            $gpuAccelerated = "False"
        }
    } else {
        $gpuAccelerated = "False"
    }
} else {
    Write-Host "[ERROR] Failed to install/verify faster-whisper." -ForegroundColor Red
    $gpuAccelerated = "False"
}

# 나머지 requirements.txt 패키지들 설치
Write-Host "[*] Installing auxiliary packages from requirements.txt..." -ForegroundColor Yellow
pip install streamlit plotly pandas matplotlib numpy scipy scikit-learn vosk python-docx yt-dlp

Write-Host "[OK] Dependencies ready. (GPU Acceleration: $gpuAccelerated)" -ForegroundColor Green

# 6. Make directories
$paths = @("C:\ameva\input", "C:\ameva\outputs", "C:\ameva\AMEVA-STT-Agent\db")
foreach ($p in $paths) {
    if (-not (Test-Path $p)) {
        New-Item -ItemType Directory -Force -Path $p | Out-Null
    }
}

# 7. Launch
Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
if ($gpuAccelerated -eq "True") {
    Write-Host "   🚀 Launching AMEVA STT Enterprise (GPU CUDA ACCELERATED)..." -ForegroundColor Green
} else {
    Write-Host "   🚀 Launching AMEVA STT Enterprise (CPU FALLBACK MODE)..." -ForegroundColor Yellow
}
Write-Host "========================================================" -ForegroundColor Green

$env:AMEVA_GPU_ACCELERATED = "$gpuAccelerated"
$env:AMEVA_GPU_NAME = "$gpuName"

streamlit run app.py

