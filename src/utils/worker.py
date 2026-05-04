from PyQt6.QtCore import QThread, pyqtSignal
from src.core.pipeline import HybridPipeline
import os

class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    chart_signal = pyqtSignal(object, object) # pca_embeddings, labels
    finished_signal = pyqtSignal(str) # result file path

    def __init__(self, input_dir, output_dir):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir

    def run(self):
        pipeline = HybridPipeline()
        
        # Discover audio files
        if not os.path.exists(self.input_dir):
            self.log_signal.emit(f"[Error] Input directory {self.input_dir} not found.")
            return

        audio_files = [f for f in os.listdir(self.input_dir) if f.endswith(('.wav', '.mp3'))]
        if not audio_files:
            self.log_signal.emit("[Error] No audio files found.")
            return

        for audio in audio_files:
            audio_path = os.path.join(self.input_dir, audio)
            self.log_signal.emit(f"\n[Worker] Starting processing for {audio}")
            
            # Run pipeline
            final_segments, pca_embeddings, labels, out_json = pipeline.process_audio(
                audio_path, self.output_dir, 
                logger_callback=lambda msg: self.log_signal.emit(msg)
            )
            
            # Emit results for UI update
            self.chart_signal.emit(pca_embeddings, labels)
            self.finished_signal.emit(out_json)
            
        self.log_signal.emit("\n[Worker] Batch processing finished.")
