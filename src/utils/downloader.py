import os
import requests
from PyQt6.QtCore import QThread, pyqtSignal

class ModelDownloader(QThread):
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, model_name, save_dir):
        super().__init__()
        self.model_name = model_name
        self.save_dir = save_dir
        
        # Whisper.cpp GGML Q5_0 양자화 모델 URL 매핑 (효율성 극대화)
        self.url_map = {
            "small": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin",
            "medium": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium-q5_0.bin",
            "turbo": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin",
            "large": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"
        }

    def run(self):
        url = self.url_map.get(self.model_name)
        if not url:
            self.log_signal.emit(f"❌ 알 수 없는 모델: {self.model_name}")
            self.finished_signal.emit(False)
            return

        filename = os.path.basename(url)
        save_path = os.path.join(self.save_dir, filename)
        os.makedirs(self.save_dir, exist_ok=True)

        self.log_signal.emit(f"📥 다운로드 시작: {filename}...")
        
        try:
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress_signal.emit(progress)
            
            self.log_signal.emit(f"✅ 다운로드 완료: {save_path}")
            self.finished_signal.emit(True)
        except Exception as e:
            self.log_signal.emit(f"❌ 다운로드 오류: {str(e)}")
            self.finished_signal.emit(False)
