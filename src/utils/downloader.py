import os
import requests
import threading

class ModelDownloader(threading.Thread):
    def __init__(self, model_name, save_dir, progress_callback=None, log_callback=None, finished_callback=None):
        super().__init__()
        self.model_name = model_name
        self.save_dir = save_dir
        self.progress_callback = progress_callback
        self.log_callback = log_callback
        self.finished_callback = finished_callback
        
        # Whisper.cpp GGML Q5_0 양자화 모델 URL 매핑 (효율성 극대화)
        self.url_map = {
            "tiny": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
            "small": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small-q5_1.bin",
            "medium": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium-q5_0.bin",
            "turbo": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin",
            "large": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin"
        }

    def run(self):
        url = self.url_map.get(self.model_name)
        if not url:
            if self.log_callback:
                self.log_callback(f"❌ 알 수 없는 모델: {self.model_name}")
            if self.finished_callback:
                self.finished_callback(False)
            return

        filename = os.path.basename(url)
        save_path = os.path.join(self.save_dir, filename)
        os.makedirs(self.save_dir, exist_ok=True)

        if self.log_callback:
            self.log_callback(f"📥 다운로드 시작: {filename}...")
        
        try:
            response = requests.get(url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            downloaded_size = 0
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0 and self.progress_callback:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress_callback(progress)
            
            if self.log_callback:
                self.log_callback(f"✅ 다운로드 완료: {save_path}")
            if self.finished_callback:
                self.finished_callback(True)
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"❌ 다운로드 오류: {str(e)}")
            if self.finished_callback:
                self.finished_callback(False)
