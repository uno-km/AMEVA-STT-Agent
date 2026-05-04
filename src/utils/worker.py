from PyQt6.QtCore import QThread, pyqtSignal
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager
import os
import time
import csv
from datetime import datetime

class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    chart_signal = pyqtSignal(object, object)
    finished_signal = pyqtSignal(str)

    def __init__(self, input_dir, output_dir):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        
        # Load batch DB info from settings
        batch_settings = settings_manager.get("batch")
        self.db_file = batch_settings.get("db_file", "stt_batch_log.csv")
        self.exception_db_file = batch_settings.get("exception_db_file", "stt_exception_log.csv")
        self.audio_extensions = (".wav", ".m4a", ".mp3", ".flac", ".aac", ".ogg", ".opus")

    def run(self):
        pipeline = STTPipeline()
        batch_id = datetime.now().strftime("%Y%m%d_%H%M")
        
        self.log_signal.emit(f"🚀 배치 작업 시작 (Batch ID: {batch_id})")
        
        # Ensure directories
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # 1. Scan files
        audio_files = []
        for root, _, filenames in os.walk(self.input_dir):
            for fname in filenames:
                if fname.lower().endswith(self.audio_extensions):
                    rel_path = os.path.relpath(os.path.join(root, fname), self.input_dir)
                    audio_files.append((rel_path, os.path.join(root, fname)))
        
        if not audio_files:
            self.log_signal.emit("⚠️ 입력 폴더에 지원되는 오디오 파일이 하나도 없습니다.")
            return

        # 2. Load DB and filter
        processed_files = self.load_processed_files()
        work_queue = [f for f in audio_files if f[0] not in processed_files]
        
        if not work_queue:
            self.log_signal.emit(f"✅ 모든 파일({len(audio_files)}개)이 이미 처리되었습니다. 새로 분석할 파일이 없습니다.")
            return

        self.log_signal.emit(f"[*] 총 {len(audio_files)}개 파일 발견 -> {len(work_queue)}개 신규 파일 분석 시작")

        for rel_path, full_path in work_queue:
            self.log_signal.emit(f"\n[Processing] {rel_path} ...")
            start_ts = time.time()
            
            try:
                # Execute Pipeline (4개 값 반환: json_path, embeddings, labels, cluster_db_path)
                final_json_path, embeddings, labels, cluster_db_path = pipeline.execute(
                    full_path, 
                    self.output_dir, 
                    logger_callback=lambda msg: self.log_signal.emit(msg)
                )
                
                duration = time.time() - start_ts
                self.log_batch_result(rel_path, final_json_path, batch_id, duration, "SUCCESS", "", cluster_db_path)
                
                # Update UI
                self.chart_signal.emit(embeddings, labels)
                self.finished_signal.emit(final_json_path)
                
            except Exception as e:
                duration = time.time() - start_ts
                err_msg = str(e)
                self.log_signal.emit(f"❌ 오류 발생: {err_msg}")
                self.log_batch_result(rel_path, "", batch_id, duration, "FAIL", err_msg)

        self.log_signal.emit(f"\n✅ 모든 배치 작업이 종료되었습니다. (ID: {batch_id})")

    def load_processed_files(self):
        processed = set()
        if not os.path.exists(self.db_file):
            return processed
        try:
            with open(self.db_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("status", "").upper() == "SUCCESS":
                        processed.add(row.get("original_filename"))
        except:
            pass
        return processed

    def log_batch_result(self, original_filename, output_filename, batch_id, duration, status, error="", cluster_db_path=""):
        file_exists = os.path.exists(self.db_file)
        fieldnames = [
            "timestamp", "original_filename", "output_filename", 
            "batch_id", "duration", "status", "error", "cluster_db_path"
        ]
        
        with open(self.db_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "original_filename": original_filename,
                "output_filename": output_filename,
                "batch_id": batch_id,
                "duration": f"{duration:.2f}",
                "status": status,
                "error": error,
                "cluster_db_path": cluster_db_path
            })
        
        if error:
            self.log_exception(original_filename, batch_id, error)

    def log_exception(self, original_filename, batch_id, error):
        file_exists = os.path.exists(self.exception_db_file)
        fieldnames = ["timestamp", "batch_id", "original_filename", "error"]
        with open(self.exception_db_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "batch_id": batch_id,
                "original_filename": original_filename,
                "error": error
            })
