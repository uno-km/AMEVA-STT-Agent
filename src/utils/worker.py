from PyQt6.QtCore import QThread, pyqtSignal
from src.core.pipeline import STTPipeline
import os
import time

class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    chart_signal = pyqtSignal(object, object) # For PCA scatter (embeddings, labels)
    finished_signal = pyqtSignal(str) # For opening the final JSON/TXT file

    def __init__(self, input_dir, output_dir):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir

    def run(self):
        pipeline = STTPipeline()
        
        self.log_signal.emit(f"[*] 배치 워커 스레드 시작")
        self.log_signal.emit(f"[*] 입력 폴더: {self.input_dir}")
        self.log_signal.emit(f"[*] 출력 폴더: {self.output_dir}")

        if not os.path.exists(self.input_dir):
            self.log_signal.emit(f"[Error] 입력 폴더를 찾을 수 없습니다: {self.input_dir}")
            return

        audio_files = [f for f in os.listdir(self.input_dir) if f.lower().endswith(('.wav', '.mp3', '.m4a'))]
        if not audio_files:
            self.log_signal.emit("[Error] 처리할 오디오 파일이 없습니다.")
            return

        os.makedirs(self.output_dir, exist_ok=True)

        for audio in audio_files:
            audio_path = os.path.join(self.input_dir, audio)
            self.log_signal.emit(f"\n[Worker] 처리를 시작합니다: {audio}")
            
            # 파이프라인 실행 (로깅 콜백 연결)
            try:
                final_json_path, embeddings, labels = pipeline.execute(
                    audio_path, 
                    self.output_dir, 
                    logger_callback=lambda msg: self.log_signal.emit(msg)
                )
                
                # GUI 차트 및 뷰어 업데이트를 위한 시그널 방출
                self.chart_signal.emit(embeddings, labels)
                self.finished_signal.emit(final_json_path)
            except Exception as e:
                self.log_signal.emit(f"[Error] {audio} 처리 중 오류 발생: {str(e)}")
            
            time.sleep(0.5)

        self.log_signal.emit("\n[Worker] 모든 배치 작업이 완료되었습니다.")
