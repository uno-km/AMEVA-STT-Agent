import multiprocessing
import os
import time
import json
import numpy as np
import subprocess
import wave
import traceback
import queue
from pywhispercpp.model import Model
from src.core.settings_manager import settings_manager
from datetime import datetime
from vosk import Model as VoskModel, SpkModel, KaldiRecognizer
import math
import random

# --- 독립적인 병렬 워커 함수들 (Multiprocessing을 위해 최상단 레벨에 정의) ---

def worker_stt(audio_path, model_size, language, threads, output_queue, config=None):
    """
    GGML (whisper.cpp) 전사 워커 (CPU 전용, 멀티프로세스)
    """
    config = config or {}
    max_len = config.get("max_len", 20)
    split_on_word = config.get("split_on_word", True)
    
    # C-level stderr 가로채기 설정
    import os, sys, threading
    try:
        r_fd, w_fd = os.pipe()
        os.dup2(w_fd, 2) # stderr(2)를 파이프의 쓰기 끝으로 복제
        
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

    output_queue.put(("log", f"[STT Worker] GGML 엔진 시작: 모델({model_size}), 언어({language})"))
    start = time.time()

    # GPU 가속 상태 진단 및 VRAM 경고
    try:
        import torch
        cuda_avail = torch.cuda.is_available()
        if cuda_avail:
            device_name = torch.cuda.get_device_name(0)
            total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            output_queue.put(("system", f"🟢 GPU 가속 활성화: {device_name} (VRAM: {total_vram:.1f} GB)"))
            if model_size in ["large", "turbo"] and total_vram < 8.0:
                output_queue.put(("system", f"⚠️ 경고: '{model_size}' 모델은 약 6~8GB VRAM을 요구합니다. 현재 VRAM({total_vram:.1f}GB)이 부족할 수 있습니다. 속도 저하 또는 OOM이 발생하는 경우 small 또는 medium 모델 사용을 권장합니다."))
        else:
            output_queue.put(("system", "🟡 CPU 전용 모드로 동작 중 (CUDA 미적용)"))
    except Exception as e:
        output_queue.put(("system", f"🟡 하드웨어 가속 진단 실패: {str(e)} (CPU 모드로 구동)"))
    
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
        model_path = None
        # 사용자 지정 경로 여부 확인 (파일 시스템에 직접 존재하는 경우)
        if os.path.isfile(model_size):
            model_path = model_size
            model_name = os.path.basename(model_path)
        else:
            from src.core.settings_manager import settings_manager
            model_dir = settings_manager.get("models_dir", r"C:\ameva\models\stt")
            os.makedirs(model_dir, exist_ok=True)
            
            base_filename = f"ggml-{model_size}"
            if model_size == "turbo": base_filename = "ggml-large-v3-turbo"
            elif model_size == "large": base_filename = "ggml-large-v3"
            
            if os.path.exists(model_dir):
                for f in os.listdir(model_dir):
                    if f.startswith(base_filename) and f.endswith(".bin") and os.path.getsize(os.path.join(model_dir, f)) > 1024*1024:
                        model_path = os.path.join(model_dir, f)
                        break
            
            # pywhispercpp가 인식할 수 있는 모델 이름으로 매핑
            model_name = model_size
            if model_size == "turbo": model_name = "large-v3-turbo"
            elif model_size == "large": model_name = "large-v3"

        if not model_path:
            output_queue.put(("system", f"⚠️ 유효한 모델 파일 없음. 신규 다운로드 시도: {model_name}"))
            from pywhispercpp.utils import download_model
            try:
                download_model(model_name, download_dir=model_dir)
            except Exception as e:
                output_queue.put(("system", f"❌ 다운로드 실패: {e}"))
            model = Model(model_name, models_dir=model_dir, n_threads=threads)
        else:
            output_queue.put(("system", f"⚙️ 엔진 초기화: {os.path.basename(model_path)} 로드 중..."))
            model = Model(model_path, n_threads=threads)
            output_queue.put(("system", f"✅ 모델 로드 완료"))
            
        segments = model.transcribe(
            audio_path, 
            language=language if language != "auto" else None,
            new_segment_callback=new_segment_callback,
            max_len=max_len if max_len > 0 else None,
            split_on_word=split_on_word,
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

def worker_diarization_forced(audio_path, stt_segments, output_queue):
    """
    STT 세그먼트의 시간 정보를 기반으로 Vosk에 정확히 잘라진 오디오를 밀어넣어
    1:1 매핑되는 화자 벡터(X-Vector)를 강제 추출합니다.
    """
    output_queue.put(("log", f"[Diarization Worker] Forced Diarization 가동 중 (총 {len(stt_segments)}개 문장)..."))
    start_time = time.time()
    
    model_path = r"C:\ameva\models\stt\vosk\ko-model"
    spk_model_path = r"C:\ameva\models\stt\vosk\spk-model"
    
    if not os.path.exists(model_path) or not os.path.exists(spk_model_path):
        output_queue.put(("log", f"❌ 치명적 오류: Vosk 화자 모델 폴더가 삭제되었습니다!"))
        output_queue.put(("system", f"⚠️ Vosk 모델 누락!"))
        output_queue.put(("dia_result", ([], [])))
        return

    try:
        model = VoskModel(model_path)
        spk_model = SpkModel(spk_model_path)
        
        wf = wave.open(audio_path, "rb")
        framerate = wf.getframerate()
        
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
            output_queue.put(("system", "❌ 오디오 포맷 오류 (16kHz Mono PCM WAV 필요)"))
            output_queue.put(("dia_result", ([], [])))
            return

        vectors = []
        valid_indices = []
        
        for i, seg in enumerate(stt_segments):
            start_frame = int(seg['start'] * framerate)
            end_frame = int(seg['end'] * framerate)
            num_frames = end_frame - start_frame
            
            if num_frames <= 0: continue
                
            wf.setpos(start_frame)
            data = wf.readframes(num_frames)
            
            rec = KaldiRecognizer(model, framerate)
            rec.SetWords(True)
            rec.SetSpkModel(spk_model)
            
            rec.AcceptWaveform(data)
            res = json.loads(rec.FinalResult())
            
            if 'spk' in res:
                vectors.append(res['spk'])
                valid_indices.append(i)
                if len(vectors) % 10 == 0:
                    output_queue.put(("log", f"[Diarization] 현재 {len(vectors)}개의 화자 지문 추출 완료..."))

        elapsed = time.time() - start_time
        output_queue.put(("log", f"[Diarization Worker] 완료 ({elapsed:.1f}초) - {len(vectors)}개 화자 지문 추출 성공!"))
        output_queue.put(("dia_result", (vectors, valid_indices)))
    except Exception as e:
        output_queue.put(("system", f"❌ Diarization Error:\n{traceback.format_exc()}"))
        output_queue.put(("dia_result", ([], [])))

# --- 수학 연산 유틸리티 ---

def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    return dot / (mag1 * mag2) if mag1 * mag2 > 0 else 0.0

def kmeans_clustering(vectors, k=2, max_iter=10):
    if not vectors or k <= 0: return [], []
    if len(vectors) <= k: return list(range(len(vectors))), vectors
    centroids = random.sample(vectors, k)
    labels = []
    for _ in range(max_iter):
        labels = []
        clusters = [[] for _ in range(k)]
        for v in vectors:
            sims = [cosine_similarity(v, c) for c in centroids]
            best_idx = sims.index(max(sims))
            labels.append(best_idx)
            clusters[best_idx].append(v)
        for i in range(k):
            if clusters[i]:
                dim = len(vectors[0])
                centroids[i] = [sum(c[d] for c in clusters[i]) / len(clusters[i]) for d in range(dim)]
    return labels, centroids

def pca_reduce(vectors, dims=2):
    if not vectors: return []
    if len(vectors) < 2: return [v[:dims] for v in vectors]
    try:
        X = np.array(vectors)
        X_centered = X - X.mean(axis=0)
        if np.all(X_centered == 0): return [v[:dims] for v in vectors]
        cov = np.cov(X_centered, rowvar=False)
        eig_vals, eig_vecs = np.linalg.eigh(cov)
        idx = np.argsort(eig_vals)[::-1]
        top_vecs = eig_vecs[:, idx[:dims]]
        return np.dot(X_centered, top_vecs).tolist()
    except:
        return [v[:dims] for v in vectors]

# --- 메인 파이프라인 오케스트레이터 ---

class STTPipeline:
    def __init__(self):
        pass

    def convert_to_wav(self, input_path, log_callback=None):
        needs_conversion = True
        if input_path.lower().endswith(".wav"):
            try:
                with wave.open(input_path, "rb") as wf:
                    if wf.getnchannels() == 1 and wf.getframerate() == 16000 and wf.getsampwidth() == 2:
                        needs_conversion = False
            except: pass
        if not needs_conversion: return input_path
        output_path = os.path.splitext(input_path)[0] + "_converted.wav"
        if log_callback: log_callback(f"[Pipeline] 오디오 변환 중 (16kHz Mono): {os.path.basename(input_path)}")
        try:
            command = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path]
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path
        except Exception as e:
            if log_callback: log_callback(f"[Error] ffmpeg 변환 실패: {str(e)}")
            raise RuntimeError(f"ffmpeg 변환 실패: {str(e)}") from e

    def execute(self, audio_path, output_dir, logger_callback=None, system_callback=None, task_id=None, diarization_enabled=True, batch_id=None):
        def log(msg): 
            if logger_callback: logger_callback(msg)
        def sys_log(msg): 
            if system_callback: system_callback(msg)
            
        log(f"[Pipeline] 파일 분석 준비 중: {audio_path}")
        processed_audio = self.convert_to_wav(audio_path, log)
        
        stt_config = settings_manager.get("stt")
        model_size = stt_config.get("model", "medium").split()[0]
        language = stt_config.get("language", "ko")
        threads = int(stt_config.get("threads", 4))
        num_speakers = stt_config.get("speakers", 2)

        # GPU 가용 여부 사전 검사
        try:
            import torch
            if torch.cuda.is_available():
                gpu_info = f"🟢 GPU 가속 가능: {torch.cuda.get_device_name(0)}"
            else:
                gpu_info = "🟡 CPU Mode (GPU 가속 미활성)"
        except:
            gpu_info = "🟡 CPU Mode (진단 라이브러리 누락)"
        log(f"[Pipeline] {gpu_info} | 대상 모델: {model_size} | 언어: {language}")

        manager = multiprocessing.Manager()
        q = manager.Queue()
        
        # Phase 1: STT
        p_stt = multiprocessing.Process(target=worker_stt, args=(processed_audio, model_size, language, threads, q, stt_config))
        p_stt.start()
        
        stt_data = []
        while p_stt.is_alive() or not q.empty():
            try:
                key, val = q.get(timeout=0.5)
                if key == "log": log(val)
                elif key == "system": sys_log(val)
                elif key == "stt_result": stt_data = val
            except queue.Empty:
                if p_stt.exitcode is not None and p_stt.exitcode != 0:
                    log(f"❌ STT 프로세스 비정상 종료 (exitcode={p_stt.exitcode})")
                    break
        p_stt.join()
        
        if not stt_data:
            log("[Error] STT 결과가 없습니다. (모델 로드 실패 또는 오디오 에러)")
            return None, [], [], None, [], ""

        if diarization_enabled:
            log(f"[Pipeline] STT 완료. {len(stt_data)}개 문장 기반 Forced Diarization 시작...")

            # Phase 2: Forced Diarization
            p_dia = multiprocessing.Process(target=worker_diarization_forced, args=(processed_audio, stt_data, q))
            p_dia.start()
            
            dia_vectors_list, valid_indices = [], []
            while p_dia.is_alive() or not q.empty():
                try:
                    key, val = q.get(timeout=0.5)
                    if key == "log": log(val)
                    elif key == "system": sys_log(val)
                    elif key == "dia_result": dia_vectors_list, valid_indices = val
                except queue.Empty:
                    if p_dia.exitcode is not None and p_dia.exitcode != 0:
                        log(f"❌ DIA 프로세스 비정상 종료 (exitcode={p_dia.exitcode})")
                        break
            p_dia.join()
            
            log(f"[Pipeline] Diarization 완료. K-Means 군집화(K={num_speakers}) 시작...")
            
            if dia_vectors_list:
                labels, centroids = kmeans_clustering(dia_vectors_list, k=num_speakers)
                pca_coords = pca_reduce(dia_vectors_list)
            else:
                labels, centroids, pca_coords = [], [], []

            for seg in stt_data: seg["speaker"] = "Unknown"
            for vector_idx, stt_idx in enumerate(valid_indices):
                best_label = labels[vector_idx]
                stt_data[stt_idx]["speaker"] = f"Speaker {best_label}"
        else:
            log("[Pipeline] 화자분리(Diarization)가 비활성화되었습니다. STT 결과만 생성합니다.")
            labels, centroids, pca_coords, valid_indices = [], [], [], []
            for seg in stt_data: seg["speaker"] = "STT-Only"

        dia_texts = []
        for vector_idx, stt_idx in enumerate(valid_indices):
            # Diarization 활성화된 경우에만 시간 정보 로그 생성 (UI 표시용)
            ts = stt_data[stt_idx]["start"]
            mins = int(ts // 60)
            secs = int(ts % 60)
            text_preview = stt_data[stt_idx]["text"][:50]
            if len(stt_data[stt_idx]["text"]) > 50: text_preview += "..."
            dia_texts.append(f"[{mins:02d}:{secs:02d}] {text_preview}")
            
        if not diarization_enabled:
            # 비활성화 시 요약 로그만 생성
            dia_texts = [f"STT 완료: {len(stt_data)}개 문장"]

        # 저장 로직
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        if task_id is not None: base_name = f"{task_id}_{base_name}"
        final_json_path = os.path.join(output_dir, f"{base_name}.json")
        final_txt_path = os.path.join(output_dir, f"{base_name}.txt")
        db_dir = r"c:\ameva\AMEVA-STT-Agent\db\clusters"
        if batch_id:
            db_dir = os.path.join(db_dir, batch_id)
        os.makedirs(db_dir, exist_ok=True)
        final_cluster_path = os.path.join(db_dir, f"{base_name}_clusters.json")



        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(stt_data, f, indent=4, ensure_ascii=False)
        with open(final_txt_path, "w", encoding="utf-8") as f:
            for s in stt_data:
                f.write(f"[{s['start']:.2f} - {s['end']:.2f}] {s['speaker']}: {s['text']}\n")
        
        cluster_data = {
            "embeddings": pca_coords, "labels": labels, "texts": dia_texts,
            "original_file": audio_path, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(final_cluster_path, "w", encoding="utf-8") as f:
            json.dump(cluster_data, f)
                
        # 전체 텍스트 합산
        full_text = " ".join([s.get("text", "").strip() for s in stt_data])

        return final_json_path, np.array(pca_coords), labels, final_cluster_path, dia_texts, full_text
