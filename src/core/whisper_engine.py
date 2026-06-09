import os
import time
import queue
import traceback
import multiprocessing
import threading
from pywhispercpp.model import Model

class WhisperEngineCPU:
    def __init__(self, model_size, language="ko", threads=4, config=None):
        self.model_size = model_size
        self.language = language if language != "auto" else None
        self.threads = threads
        self.config = config or {}
        self.max_len = self.config.get("max_len", 20)
        self.split_on_word = self.config.get("split_on_word", True)

    def _setup_model_path(self):
        if os.path.isfile(self.model_size):
            return self.model_size, os.path.basename(self.model_size)
        
        model_dir = r"C:\ameva\AI_Models\ggml"
        os.makedirs(model_dir, exist_ok=True)
        
        base_filename = f"ggml-{self.model_size}"
        if self.model_size == "turbo": base_filename = "ggml-large-v3-turbo"
        elif self.model_size == "large": base_filename = "ggml-large-v3"
        
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.startswith(base_filename) and f.endswith(".bin") and os.path.getsize(os.path.join(model_dir, f)) > 1024*1024:
                    return os.path.join(model_dir, f), self.model_size
        
        model_name = self.model_size
        if self.model_size == "turbo": model_name = "large-v3-turbo"
        elif self.model_size == "large": model_name = "large-v3"
        return None, model_name

    def process(self, audio_path, output_queue):
        # C-level stderr 가로채기 설정
        try:
            r_fd, w_fd = os.pipe()
            os.dup2(w_fd, 2)
            
            def engine_log_reader():
                try:
                    pending = ""
                    while True:
                        chunk = os.read(r_fd, 1024).decode('utf-8', errors='ignore')
                        if not chunk: break
                        pending += chunk
                        while "\n" in pending:
                            line, pending = pending.split("\n", 1)
                            line = line.strip()
                            if line:
                                output_queue.put(("system", f"⚙️ {line}"))
                except:
                    pass
            
            log_thread = threading.Thread(target=engine_log_reader, daemon=True)
            log_thread.start()
        except:
            pass

        output_queue.put(("log", f"[STT Worker] GGML 엔진 시작: 모델({self.model_size}), 언어({self.language})"))
        start = time.time()
        
        def format_ts(seconds):
            ms = int((seconds % 1) * 1000)
            s = int(seconds % 60)
            m = int((seconds // 60) % 60)
            h = int(seconds // 3600)
            return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

        def new_segment_callback(segment):
            ts_start = format_ts(segment.t0 / 100.0)
            ts_end = format_ts(segment.t1 / 100.0)
            text = segment.text.strip()
            if text:
                msg = f"[{ts_start} --> {ts_end}]  {text}"
                output_queue.put(("log", msg))
        
        try:
            model_path, model_name = self._setup_model_path()

            if not model_path:
                output_queue.put(("system", f"⚠️ 유효한 모델 파일 없음. 신규 다운로드 시도: {model_name}"))
                model = Model(model_name, models_dir=r"C:\ameva\AI_Models\ggml", n_threads=self.threads)
            else:
                output_queue.put(("system", f"⚙️ 엔진 초기화: {os.path.basename(model_path)} 로드 중..."))
                model = Model(model_path, n_threads=self.threads)
                output_queue.put(("system", f"✅ 모델 로드 완료"))
                
            segments = model.transcribe(
                audio_path, 
                language=self.language,
                new_segment_callback=new_segment_callback,
                max_len=self.max_len if self.max_len > 0 else None,
                split_on_word=self.split_on_word,
            )

            results = []
            for s in segments:
                results.append({
                    "start": s.t0 / 100.0,
                    "end": s.t1 / 100.0,
                    "text": s.text.strip()
                })
                
            elapsed = time.time() - start
            output_queue.put(("log", f"[STT Worker] 완료 ({elapsed:.1f}초) - {len(results)}개 문장 추출"))
            output_queue.put(("stt_result", results))
        except Exception as e:
            output_queue.put(("log", f"[STT Worker Error]\n{traceback.format_exc()}"))
            output_queue.put(("stt_result", []))

def run_whisper_process(audio_path, model_size, language, threads, output_queue, config):
    engine = WhisperEngineCPU(model_size, language, threads, config)
    engine.process(audio_path, output_queue)
