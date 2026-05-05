from PyQt6.QtCore import QThread, pyqtSignal
from src.core.pipeline import STTPipeline
from src.core.settings_manager import settings_manager
import os
import time
import csv
from datetime import datetime

class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    system_log_signal = pyqtSignal(str) # 시스템 로그 전용 신호 추가
    chart_signal = pyqtSignal(object, object, object) # (embeddings, labels, texts)
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
        self.task_id_counter = self._load_next_task_id()

    def _load_next_task_id(self):
        """
        기존 CSV에서 가장 높은 TASK-XXXX 번호를 찾아 다음 번호를 반환합니다.
        """
        if not os.path.exists(self.db_file):
            return 1
        try:
            import re
            max_num = 0
            with open(self.db_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    tid = row.get("task_id", "")
                    if tid:
                        # "TASK-0005" -> 5 추출
                        match = re.search(r"TASK-(\d+)", tid)
                        if match:
                            num = int(match.group(1))
                            if num > max_num:
                                max_num = num
                        elif tid.isdigit(): # 하위 호환성 (숫자만 있는 경우)
                            num = int(tid)
                            if num > max_num:
                                max_num = num
            return max_num + 1
        except Exception as e:
            print(f"Task ID Loading Error: {e}")
            return 1

    def run(self):
        pipeline = STTPipeline()
        batch_id = datetime.now().strftime("%Y%m%d_%H%M")
        
        self.log_signal.emit(f"🚀 배치 작업 시작 (Batch ID: {batch_id})")
        self.log_signal.emit(f"[*] 입력 폴더 스캔 중: {self.input_dir}")
        
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
        
        self.log_signal.emit(f"[*] 총 {len(audio_files)}개의 오디오 파일 발견")

        # 2. Load DB and filter
        processed_files = self.load_processed_files()
        work_queue = []
        for rel_path, full_path in audio_files:
            if rel_path in processed_files:
                self.log_signal.emit(f"[-] Skip: {rel_path} (이미 SUCCESS 기록이 있음)")
            else:
                work_queue.append((rel_path, full_path))
        
        if not work_queue:
            if not audio_files:
                self.log_signal.emit("⚠️ 입력 폴더에 지원되는 오디오 파일이 하나도 없습니다.")
            else:
                self.log_signal.emit(f"✅ 모든 파일({len(audio_files)}개)이 이미 처리되었습니다. 새로 분석할 파일이 없습니다.")
            return

        self.log_signal.emit(f"▶️ 신규 분석 시작: {len(work_queue)}개 파일 대기 중")

        for rel_path, full_path in work_queue:
            self.log_signal.emit(f"\n[Processing] {rel_path} ...")
            start_ts = time.time()
            task_id_str = f"TASK-{self.task_id_counter:04d}"
            self.task_id_counter += 1
            
            try:
                # Get current config snapshot for logging
                stt_config = settings_manager.get("stt")
                
                # Execute Pipeline
                final_json_path, embeddings, labels, cluster_db_path, dia_texts = pipeline.execute(
                    full_path, 
                    self.output_dir, 
                    logger_callback=lambda msg: self.log_signal.emit(msg),
                    system_callback=lambda msg: self.system_log_signal.emit(msg),
                    task_id=task_id_str
                )
                
                duration = time.time() - start_ts
                self.log_batch_result(rel_path, final_json_path, batch_id, duration, "SUCCESS", "", cluster_db_path, stt_config, task_id_str)
                self._write_cluster_mapping(task_id_str, rel_path, cluster_db_path)
                
                # Update UI
                self.chart_signal.emit(embeddings, labels, dia_texts)
                self.finished_signal.emit(final_json_path)
                
            except Exception as e:
                duration = time.time() - start_ts
                err_msg = str(e)
                self.log_signal.emit(f"❌ 오류 발생: {err_msg}")
                self.log_batch_result(rel_path, "", batch_id, duration, "FAIL", err_msg, "", settings_manager.get("stt"), task_id_str)
                self._write_cluster_mapping(task_id_str, rel_path, "")

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

    def log_batch_result(self, original_filename, output_filename, batch_id, duration, status, error="", cluster_db_path="", stt_config=None, task_id=None):
        stt_config = stt_config or {}
        fieldnames = [
            "timestamp", "original_filename", "output_filename", 
            "batch_id", "duration", "status", "error", "cluster_db_path",
            "model", "language", "threads", "speakers", "max_offset", 
            "max_len", "split_on_word", "vad_enabled", "task_id"
        ]
        
        file_exists = os.path.exists(self.db_file)
        
        # 지능형 헤더 확장 로직 (기존 파일 컬럼 미달 시 자동 업그레이드)
        if file_exists:
            try:
                with open(self.db_file, "r", encoding="utf-8") as f:
                    header = f.readline().strip().split(",")
                    if len(header) < len(fieldnames):
                        # 임시 메모리에 로드 후 헤더 갈아끼우기
                        with open(self.db_file, "r", encoding="utf-8") as rf:
                            rows = list(csv.DictReader(rf))
                        with open(self.db_file, "w", encoding="utf-8", newline="") as wf:
                            writer = csv.DictWriter(wf, fieldnames=fieldnames)
                            writer.writeheader()
                            for r in rows:
                                writer.writerow(r) # 없는 컬럼은 빈 값으로 자동 처리됨
            except Exception as e:
                print(f"Header update failed: {e}")

        with open(self.db_file, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not os.path.exists(self.db_file) or os.path.getsize(self.db_file) == 0:
                writer.writeheader()
            
            row_data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "original_filename": original_filename,
                "output_filename": output_filename,
                "batch_id": batch_id,
                "duration": f"{duration:.2f}",
                "status": status,
                "error": error,
                "cluster_db_path": cluster_db_path,
                "model": stt_config.get("model", ""),
                "language": stt_config.get("language", ""),
                "threads": stt_config.get("threads", ""),
                "speakers": stt_config.get("speakers", ""),
                "max_offset": stt_config.get("max_offset", ""),
                "max_len": stt_config.get("max_len", ""),
                "split_on_word": stt_config.get("split_on_word", ""),
                "vad_enabled": stt_config.get("vad_enabled", ""),
                "task_id": str(task_id) if task_id is not None else ""
            }
            writer.writerow(row_data)
        
        if error:
            self.log_exception(original_filename, batch_id, error)

    def _write_cluster_mapping(self, task_id, original_filename, cluster_path):
        mapping_file = "db/cluster_mapping.csv"
        fieldnames = ["task_id", "original_filename", "cluster_db_path"]
        exists = os.path.exists(mapping_file)
        with open(mapping_file, "a", encoding="utf-8", newline="") as mf:
            writer = csv.DictWriter(mf, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow({
                "task_id": task_id,
                "original_filename": original_filename,
                "cluster_db_path": cluster_path
            })

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
