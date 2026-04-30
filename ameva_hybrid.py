import sys
# Bypass OS platform check in Vosk for Android/Termux
sys.platform = 'linux'

import os
import wave
import json
import math
import subprocess
import time
import argparse
from vosk import Model, SpkModel, KaldiRecognizer

# ==========================================
# 1. Configuration
# ==========================================
AUDIO_FILE = "/data/data/com.termux/files/home/projects/stt_benchmark/samples/test_cut_2.wav"
WHISPER_CMD = "/data/data/com.termux/files/home/projects/stt_benchmark/whisper.cpp/main"
WHISPER_MODEL_SMALL = "/data/data/com.termux/files/home/projects/stt_benchmark/whisper.cpp/models/ggml-small.bin"
WHISPER_MODEL_MEDIUM = "/data/data/com.termux/files/home/projects/stt_benchmark/whisper.cpp/models/ggml-medium.bin"

# ==========================================
# 2. Vector Operations (Pure Python)
# ==========================================
def cosine_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0: return 0.0
    return dot_product / (mag1 * mag2)

# ==========================================
# Main Execution
# ==========================================
def main():
    # CLI Arguments Setup
    parser = argparse.ArgumentParser(description="AMEVA Hybrid STT Engine (Whisper + Vosk)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--small", action="store_true", help="Use small whisper model (default)")
    group.add_argument("--medium", action="store_true", help="Use medium whisper model")
    args = parser.parse_args()

    # Model Selection
    if args.medium:
        active_whisper_model = WHISPER_MODEL_MEDIUM
        model_name = "Medium"
    else:
        active_whisper_model = WHISPER_MODEL_SMALL
        model_name = "Small"

    print("[SYSTEM] Initiating AMEVA Hybrid STT Engine (Whisper + Vosk)")
    print(f"[SYSTEM] Target Audio: {AUDIO_FILE}")
    print(f"[SYSTEM] Active Whisper Model: {model_name} ({active_whisper_model})")
    
    total_start_time = time.time()

    # ------------------------------------------
    # Phase 1: Whisper.cpp Transcription
    # ------------------------------------------
    print("\n[Phase 1] Executing Whisper.cpp for transcription...")
    phase1_start = time.time()
    
    subprocess.run([
        WHISPER_CMD, 
        "-m", active_whisper_model, 
        "-f", AUDIO_FILE, 
        "-oj", "-nt"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    whisper_json_file = AUDIO_FILE + ".json"
    if not os.path.exists(whisper_json_file):
        print("[ERROR] Whisper JSON output not found.")
        sys.exit(1)

    with open(whisper_json_file, "r", encoding="utf-8") as f:
        whisper_data = json.load(f)

    whisper_segments = []
    for segment in whisper_data.get("transcription", []):
        start_sec = segment["offsets"]["from"] / 1000.0
        end_sec = segment["offsets"]["to"] / 1000.0
        text = segment["text"].strip()
        if text:
            whisper_segments.append({"start": start_sec, "end": end_sec, "text": text})
            
    phase1_end = time.time()
    print(f"[Phase 1] Completed in {phase1_end - phase1_start:.2f} seconds.")

    # ------------------------------------------
    # Phase 2: Vosk Speaker Diarization
    # ------------------------------------------
    print("\n[Phase 2] Executing Vosk for speaker vector extraction...")
    phase2_start = time.time()
    
    try:
        model = Model("models/ko-model")
        spk_model = SpkModel("models/spk-model")
    except Exception as e:
        print(f"[ERROR] Failed to load Vosk models. Ensure 'models/ko-model' and 'models/spk-model' exist. Details: {e}")
        sys.exit(1)

    try:
        wf = wave.open(AUDIO_FILE, "rb")
    except FileNotFoundError:
        print(f"[ERROR] Audio file not found at {AUDIO_FILE}")
        sys.exit(1)
        
    rec = KaldiRecognizer(model, wf.getframerate(), spk_model)
    rec.SetWords(True)

    vosk_speakers = [] 

    while True:
        data = wf.readframes(4000)
        if len(data) == 0: break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            if 'spk' in res and 'result' in res and len(res['result']) > 0:
                vosk_speakers.append({
                    "start": res['result'][0]['start'],
                    "end": res['result'][-1]['end'],
                    "vector": res['spk']
                })

    res = json.loads(rec.FinalResult())
    if 'spk' in res and 'result' in res and len(res['result']) > 0:
        vosk_speakers.append({
            "start": res['result'][0]['start'],
            "end": res['result'][-1]['end'],
            "vector": res['spk']
        })
        
    phase2_end = time.time()
    print(f"[Phase 2] Completed in {phase2_end - phase2_start:.2f} seconds.")

    # ------------------------------------------
    # Phase 3: Timeline Synchronization (Merge)
    # ------------------------------------------
    print("\n[Phase 3] Synchronizing timelines and clustering speakers...")
    phase3_start = time.time()
    
    speaker_a_ref = vosk_speakers[0]['vector'] if vosk_speakers else None

    print("\n============================================================")
    print("[RESULT] AMEVA Hybrid STT Output")
    print("============================================================")

    for w_seg in whisper_segments:
        w_start = w_seg['start']
        w_mid = (w_seg['start'] + w_seg['end']) / 2.0
        
        matched_vector = None
        for v_seg in vosk_speakers:
            if v_seg['start'] <= w_mid <= v_seg['end']:
                matched_vector = v_seg['vector']
                break
        
        current_speaker = "Unknown"
        if matched_vector and speaker_a_ref:
            similarity = cosine_similarity(speaker_a_ref, matched_vector)
            if similarity > 0.5:
                current_speaker = "Speaker A"
            else:
                current_speaker = "Speaker B"
                
        print(f"[{w_seg['start']:>5.1f}s - {w_seg['end']:>5.1f}s] [{current_speaker}] : {w_seg['text']}")

    print("============================================================")
    
    phase3_end = time.time()
    total_end_time = time.time()
    
    print(f"\n[PROFILING] Execution Time Summary")
    print(f"  - Phase 1 (Whisper ASR) : {phase1_end - phase1_start:.2f} sec")
    print(f"  - Phase 2 (Vosk Spk)    : {phase2_end - phase2_start:.2f} sec")
    print(f"  - Phase 3 (Merge)       : {phase3_end - phase3_start:.2f} sec")
    print(f"  - Total Execution Time  : {total_end_time - total_start_time:.2f} sec")

if __name__ == "__main__":
    main()