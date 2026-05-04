import multiprocessing
from src.core.whisper_engine import WhisperEngineCPU
from src.core.vosk_engine import VoskEngineCPU
from src.diarization.clustering import DiarizationClustering
from src.core.settings_manager import settings_manager
import json
import os
import time

def run_whisper(audio_path):
    engine = WhisperEngineCPU()
    return engine.transcribe(audio_path)

def run_vosk(audio_path):
    engine = VoskEngineCPU()
    return engine.extract_speaker_embeddings(audio_path)

class HybridPipeline:
    def __init__(self):
        pass

    def process_audio(self, audio_path, output_dir, logger_callback=None):
        if logger_callback:
            logger_callback(f"[Pipeline] Starting parallel processing for {audio_path}")
            
        start_time = time.time()

        # Step 1 & 2: Parallel execution of Whisper & Vosk on CPU
        with multiprocessing.Pool(processes=2) as pool:
            whisper_result = pool.apply_async(run_whisper, (audio_path,))
            vosk_result = pool.apply_async(run_vosk, (audio_path,))
            
            # Wait for both to finish
            whisper_segments = whisper_result.get()
            vosk_embeddings = vosk_result.get()

        if logger_callback:
            logger_callback("[Pipeline] Parallel processing completed.")

        # Step 3: Clustering and Alignment
        margin = settings_manager.get("diarization", "margin")
        clustering = DiarizationClustering(margin=margin)
        
        final_segments, pca_embeddings, labels = clustering.perform_clustering(
            whisper_segments, vosk_embeddings
        )

        # Step 4: Save Result
        base_name = os.path.basename(audio_path).split('.')[0]
        out_json = os.path.join(output_dir, f"{base_name}_result.json")
        out_txt = os.path.join(output_dir, f"{base_name}_result.txt")

        os.makedirs(output_dir, exist_ok=True)
        
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(final_segments, f, ensure_ascii=False, indent=4)
            
        with open(out_txt, 'w', encoding='utf-8') as f:
            for seg in final_segments:
                f.write(f"[{seg['start']:.2f} - {seg['end']:.2f}] {seg['speaker']}: {seg['text']}\n")

        elapsed = time.time() - start_time
        if logger_callback:
            logger_callback(f"[Pipeline] Saved results to {output_dir}")
            logger_callback(f"[Pipeline] Done in {elapsed:.2f} seconds.")

        return final_segments, pca_embeddings, labels, out_json
