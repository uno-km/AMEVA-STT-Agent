#!/bin/bash

# ==============================================================================
# Vosk Offline STT Engine Manual Porting Script for Termux (Android/ARM64)
# ==============================================================================
# This script automates the process of porting the Vosk engine to the Termux
# environment, bypassing standard wheel packaging limitations by compiling the
# CFFI wrapper manually and spoofing the OS platform check.
# ==============================================================================

# 1. Define Directories and Variables
PROJECT_DIR="$HOME/projects/vosk_termux_port"
VOSK_API_URL="https://github.com/alphacep/vosk-api"
VOSK_AAR_URL="https://repo1.maven.org/maven2/com/alphacephei/vosk-android/0.3.38/vosk-android-0.3.38.aar"

# Define color codes for logging
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}[INFO] Starting Vosk manual porting process for Termux...${NC}"

# 2. Install Required System Dependencies
echo -e "\n${YELLOW}[STEP 1] Installing required build tools and libraries...${NC}"
pkg update -y
pkg install -y clang make python-dev libffi wget unzip git
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to install system dependencies. Aborting.${NC}"
    exit 1
fi

# 3. Install Python Build Dependencies
echo -e "\n${YELLOW}[STEP 2] Installing Python CFFI and build dependencies...${NC}"
pip install cffi srt websockets
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR] Failed to install Python dependencies. Aborting.${NC}"
    exit 1
fi

# 4. Setup Project Directory
echo -e "\n${YELLOW}[STEP 3] Initializing project workspace...${NC}"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR" || exit 1
rm -rf vosk-api vosk-android-0.3.38.aar libvosk.so vosk run_vosk.py

# 5. Extract libvosk.so from Android AAR
echo -e "\n${YELLOW}[STEP 4] Downloading Android AAR and extracting libvosk.so...${NC}"
wget -q "$VOSK_AAR_URL" -O vosk-android.aar
if [ ! -f "vosk-android.aar" ]; then
    echo -e "${RED}[ERROR] Failed to download Vosk AAR file. Aborting.${NC}"
    exit 1
fi
unzip -j vosk-android.aar jni/arm64-v8a/libvosk.so -d . > /dev/null 2>&1
if [ ! -f "libvosk.so" ]; then
    echo -e "${RED}[ERROR] Failed to extract libvosk.so (ARM64). Aborting.${NC}"
    exit 1
fi
echo -e "${GREEN}SUCCESS: libvosk.so extracted.${NC}"

# 6. Clone Vosk Source and Generate CFFI Wrapper
echo -e "\n${YELLOW}[STEP 5] Cloning Vosk source and generating Python CFFI wrapper...${NC}"
git clone -q "$VOSK_API_URL"
cd vosk-api/python || exit 1
python vosk_builder.py > /dev/null 2>&1
if [ ! -d "vosk" ]; then
    echo -e "${RED}[ERROR] Failed to generate 'vosk' python module. Aborting.${NC}"
    exit 1
fi

# Move the generated module to the project root
cp -r vosk "$PROJECT_DIR/"
cd "$PROJECT_DIR" || exit 1
echo -e "${GREEN}SUCCESS: Python wrapper module created and moved.${NC}"

# 7. Relocate Shared Library
echo -e "\n${YELLOW}[STEP 6] Linking shared library to the Python module...${NC}"
cp libvosk.so vosk/
echo -e "${GREEN}SUCCESS: libvosk.so moved to module directory.${NC}"

# 8. Create Execution Script with OS Spoofing
echo -e "\n${YELLOW}[STEP 7] Generating test script with OS spoofing bypass...${NC}"
cat << 'EOF' > run_vosk.py
import sys
# [Bypass] Spoofing platform check to bypass 'Unsupported platform' error in Termux
sys.platform = 'linux'

import wave
import json
import os
from vosk import Model, SpkModel, KaldiRecognizer

# Adjust this path to a valid mono WAV file for testing
AUDIO_FILE = "test.wav" 

print("[SYSTEM] Starting Vosk Offline Inference Engine...")

if not os.path.exists("models/ko-model"):
    print("[ERROR] Model directory 'models/ko-model' not found.")
    print("Please download a compatible Vosk model and place it in the models directory.")
    sys.exit(1)

model = Model("models/ko-model")

if not os.path.exists(AUDIO_FILE):
    print(f"[WARNING] Audio file '{AUDIO_FILE}' not found. Please provide a valid file to test transcription.")
    sys.exit(0)

wf = wave.open(AUDIO_FILE, "rb")
if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() not in [8000, 16000, 32000, 44100, 48000]:
    print("[ERROR] Audio file must be WAV format mono PCM.")
    sys.exit(1)

rec = KaldiRecognizer(model, wf.getframerate())
rec.SetWords(True)

print("\n[SYSTEM] Processing audio stream...\n")
while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        res = json.loads(rec.Result())
        if 'text' in res and res['text']:
            print(f"Transcript: {res['text']}")

res = json.loads(rec.FinalResult())
if 'text' in res and res['text']:
    print(f"Transcript: {res['text']}")

print("\n[SYSTEM] Audio processing completed.")
EOF
echo -e "${GREEN}SUCCESS: run_vosk.py generated.${NC}"

# 9. Final Instructions
echo -e "\n${BLUE}======================================================================${NC}"
echo -e "${GREEN}[COMPLETED] Vosk Engine Porting Successfully Finished!${NC}"
echo -e "Project Location: ${PROJECT_DIR}"
echo -e "To test the engine, please follow these steps:"
echo -e "  1. Navigate to the project directory: cd ${PROJECT_DIR}"
echo -e "  2. Download a Vosk model (e.g., Korean) and extract it to 'models/ko-model'"
echo -e "  3. Place a mono WAV file named 'test.wav' in the project directory."
echo -e "  4. Execute the test script: python run_vosk.py"
echo -e "${BLUE}======================================================================${NC}"

exit 0