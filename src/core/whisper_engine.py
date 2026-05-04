import time
import os
from src.core.settings_manager import settings_manager

class WhisperEngineCPU:
    def __init__(self):
        # Read from settings
        settings = settings_manager.get("stt")
        self.model_path = os.path.join(r"C:\ameva\AI_Models", settings.get("model", "ggml-medium-q5_0.bin"))
        self.language = settings.get("language", "ko")
        self.threads = settings.get("threads", 4)
        
    def transcribe(self, audio_path):
        """
        Mock for Whisper C++ or Python wrapper execution on CPU.
        In reality, you'd use something like faster-whisper or subprocess call to whisper-cli.
        """
        print(f"[WhisperEngine] Loading model: {self.model_path}")
        print(f"[WhisperEngine] Threads: {self.threads}, Language: {self.language}")
        print(f"[WhisperEngine] Starting transcription for {audio_path}")
        
        # Simulate processing time
        time.sleep(2)
        
        # Return mock JSON-like list of segments
        return [
            {"start": 0.0, "end": 2.5, "text": "안녕하세요 환영합니다."},
            {"start": 3.0, "end": 5.0, "text": "이것은 하이브리드 STT 테스트입니다."}
        ]
