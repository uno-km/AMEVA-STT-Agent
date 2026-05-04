import multiprocessing
import os
import time
import json
import numpy as np
import subprocess
import wave
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
    vad_enabled = config.get("vad_enabled", False)
    vad_max = config.get("vad_max_speech_duration", 5)
    vad_min = config.get("vad_min_silence_duration", 500)
    # C-level stderr 가로채기 설정
    import os, sys, threading
    try:
        r_fd, w_fd = os.pipe()
        os.dup2(w_fd, 2) # stderr(2)를 파이프의 쓰기 끝으로 복제
        
        def engine_log_reader():
            try:
                # os.fdopen을 사용하여 파일 서술자를 파이썬 파일 객체로 변환
                with os.fdopen(r_fd, 'r', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # 엔진 로그임을 표시하여 시스템 탭으로 전송
                            output_queue.put(("system", f"⚙️ {line}"))
            except:
                pass
        
        # 별도 스레드에서 엔진 로그 감시 시작
        log_thread = threading.Thread(target=engine_log_reader, daemon=True)
        log_thread.start()
    except:
        pass

    output_queue.put(("log", f"[STT Worker] GGML 엔진 시작: 모델({model_size}), 언어({language})"))
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
        # 모델 경로 설정 (C:\ameva\AI_Models\ggml)
        model_dir = r"C:\ameva\AI_Models\ggml"
        os.makedirs(model_dir, exist_ok=True)
        
        # 모델 파일명 매핑 (ggml-medium.bin 혹은 ggml-medium-q5_0.bin 등 검색)
        base_filename = f"ggml-{model_size}"
        if model_size == "turbo": base_filename = "ggml-large-v3-turbo"
        elif model_size == "large": base_filename = "ggml-large-v3"
        
        model_path = None
        if os.path.exists(model_dir):
            for f in os.listdir(model_dir):
                if f.startswith(base_filename) and f.endswith(".bin") and os.path.getsize(os.path.join(model_dir, f)) > 1024*1024:
                    model_path = os.path.join(model_dir, f)
                    break
        
        # 모델 로드 (파일이 없으면 pywhispercpp가 자동 다운로드 시도)
        if not model_path:
            output_queue.put(("system", f"⚠️ 유효한 모델 파일 없음. 신규 다운로드 시도: {base_filename}"))
            model = Model(model_size, models_dir=model_dir, n_threads=threads)
        else:
            output_queue.put(("system", f"⚙️ 엔진 초기화: {os.path.basename(model_path)} 로드 중..."))
            model = Model(model_path, n_threads=threads)
            output_queue.put(("system", f"✅ 모델 로드 완료 (ftype: 8, qntvr: 2)"))
            
        # 전사 실행 (실시간 콜백 및 고급 옵션 연결)
        segments = model.transcribe(
            audio_path, 
            language=language if language != "auto" else None,
            new_segment_callback=new_segment_callback,
            max_len=max_len if max_len > 0 else None,
            split_on_word=split_on_word,
            # pywhispercpp의 VAD 옵션은 버전에 따라 다를 수 있으므로 안전하게 처리
        )

        
        # 결과 포맷팅 (pywhispercpp는 t0, t1 단위를 1/100초로 반환함)
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
        output_queue.put(("log", f"[STT Worker Error] {str(e)}"))
        output_queue.put(("stt_result", []))

def worker_diarization(audio_path, output_queue):
    """
    Vosk 화자 성문 벡터(X-Vector) 추출 워커 (CPU 전용, 멀티프로세스)
    """
    output_queue.put(("log", f"[Diarization Worker] 화자 분석 엔진 가동 중..."))
    start = time.time()
    
    # 모델 경로 (C:\ameva\AI_Models\vosk 하위로 관리 권장)
    # 여기선 기본적으로 프로젝트 내 models 폴더 혹은 C 드라이브 탐색
    model_path = r"C:\ameva\AI_Models\vosk\ko-model"
    spk_model_path = r"C:\ameva\AI_Models\vosk\spk-model"
    
    if not os.path.exists(model_path) or not os.path.exists(spk_model_path):
        output_queue.put(("system", "⚠️ Vosk 모델을 찾을 수 없습니다. (C:\\ameva\\AI_Models\\vosk\\...)"))
        output_queue.put(("dia_result", ([], [])))
        return

    try:
        model = VoskModel(model_path)
        spk_model = SpkModel(spk_model_path)
        
        wf = wave.open(audio_path, "rb")
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
            output_queue.put(("system", "❌ 오디오 포맷 오류 (16kHz Mono PCM WAV 필요)"))
            output_queue.put(("dia_result", ([], [])))
            return

        rec = KaldiRecognizer(model, wf.getframerate(), spk_model)
        rec.SetWords(True)

        vectors = []
        timestamps = []

        while True:
            data = wf.readframes(4000)
            if len(data) == 0: break
            if rec.AcceptWaveform(data):
                res = json.loads(rec.Result())
                if 'spk' in res and 'result' in res and len(res['result']) > 0:
                    vectors.append(res['spk'])
                    timestamps.append({
                        "start": res['result'][0]['start'],
                        "end": res['result'][-1]['end']
                    })

        res = json.loads(rec.FinalResult())
        if 'spk' in res and 'result' in res and len(res['result']) > 0:
            vectors.append(res['spk'])
            timestamps.append({
                "start": res['result'][0]['start'],
                "end": res['result'][-1]['end']
            })

        elapsed = time.time() - start
        output_queue.put(("log", f"[Diarization Worker] 완료 ({elapsed:.1f}초) - {len(vectors)}개 성문 벡터 추출"))
        output_queue.put(("dia_result", (vectors, timestamps)))
    except Exception as e:
        output_queue.put(("system", f"❌ Diarization Error: {str(e)}"))
        output_queue.put(("dia_result", ([], [])))

# --- 수학 연산 유틸리티 (K-Means, PCA) ---

def cosine_similarity(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    return dot / (mag1 * mag2) if mag1 * mag2 > 0 else 0.0

def kmeans_clustering(vectors, k=2, max_iter=10):
    if not vectors or k <= 0: return [], []
    if len(vectors) <= k: return list(range(len(vectors))), vectors
    
    # 초기 중심점 랜덤 선택
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
            
        # 중심점 업데이트
        for i in range(k):
            if clusters[i]:
                dim = len(vectors[0])
                centroids[i] = [sum(c[d] for c in clusters[i]) / len(clusters[i]) for d in range(dim)]
    return labels, centroids

def pca_reduce(vectors, dims=2):
    """
    고차원(128D) 벡터를 시각화용 2D로 압축 (간이 PCA 구현)
    """
    if not vectors: return []
    import numpy as np
    try:
        X = np.array(vectors)
        X_centered = X - X.mean(axis=0)
        cov = np.cov(X_centered, rowvar=False)
        eig_vals, eig_vecs = np.linalg.eigh(cov)
        idx = np.argsort(eig_vals)[::-1]
        top_vecs = eig_vecs[:, idx[:dims]]
        return np.dot(X_centered, top_vecs).tolist()
    except:
        # Numpy 실패 시 상위 2개 차원만 반환 (담백한 폴백)
        return [v[:dims] for v in vectors]


# --- 메인 파이프라인 오케스트레이터 ---

class STTPipeline:
    def __init__(self):
        pass

    def convert_to_wav(self, input_path, log_callback=None):
        """
        비 WAV 파일을 16kHz Mono WAV로 변환합니다. (Vosk 및 STT 최적화)
        """
        if input_path.lower().endswith(".wav"):
            return input_path

        output_path = os.path.splitext(input_path)[0] + "_converted.wav"
        if log_callback: log_callback(f"[Pipeline] 변환 중: {os.path.basename(input_path)} -> wav")
        
        try:
            # ffmpeg -y -i input -ar 16000 -ac 1 output
            command = [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", "16000", "-ac", "1",
                output_path
            ]
            subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return output_path
        except Exception as e:
            if log_callback: log_callback(f"[Error] 변환 실패: {str(e)}")
            return input_path

    def execute(self, audio_path, output_dir, logger_callback=None, system_callback=None):
        """
        Multiprocessing을 통해 STT와 Diarization을 병렬로 돌리고 Phase 3에서 병합합니다.
        """
        def log(msg):
            if logger_callback: logger_callback(msg)
            
        def sys_log(msg):
            if system_callback: system_callback(msg)
            
        log(f"[Pipeline] 파일 병렬 분석 준비 중: {audio_path}")
        
        # Phase 0: 오디오 전처리 (WAV 변환)
        processed_audio = self.convert_to_wav(audio_path, log)
        
        # 설정 불러오기
        stt_config = settings_manager.get("stt")
        model_size = stt_config.get("model", "medium").split()[0]
        language = stt_config.get("language", "ko")
        threads = int(stt_config.get("threads", 4))
        
        num_speakers = stt_config.get("speakers", 2)
        max_offset = stt_config.get("max_offset", 2.0)

        # 통신용 큐 생성
        manager = multiprocessing.Manager()
        q = manager.Queue()
        
        # 프로세스 생성 (고급 설정 config 전달)
        p_stt = multiprocessing.Process(target=worker_stt, args=(processed_audio, model_size, language, threads, q, stt_config))
        p_dia = multiprocessing.Process(target=worker_diarization, args=(processed_audio, q))
        
        # 동시 시작
        p_stt.start()
        p_dia.start()
        
        # 큐에서 실시간 로그 및 결과 스트리밍
        stt_data = []
        dia_vectors_list, dia_timestamps = [], []
        finished_procs = 0
        
        while finished_procs < 2:
            key, val = q.get()
            if key == "log":
                log(val)
            elif key == "system":
                sys_log(val)
            elif key == "stt_result":
                stt_data = val
                finished_procs += 1
            elif key == "dia_result":
                dia_vectors_list, dia_timestamps = val
                finished_procs += 1
                
        p_stt.join()
        p_dia.join()
        
        log(f"[Pipeline] Phase 1, 2 완료. K-Means 군집화(K={num_speakers}) 및 텍스트 매핑 시작...")
        
        # Phase 3: 진짜 K-Means 클러스터링 수행
        if dia_vectors_list:
            labels, centroids = kmeans_clustering(dia_vectors_list, k=num_speakers)
            pca_coords = pca_reduce(dia_vectors_list)
        else:
            labels, centroids, pca_coords = [], [], []

        # Whisper 세그먼트와 화자 매핑 (시간축 기준) 및 시각화용 텍스트 추출
        dia_texts = ["(No mapping)"] * len(dia_vectors_list)
        for seg in stt_data:
            w_mid = (seg['start'] + seg['end']) / 2.0
            best_label = -1
            min_dist = float('inf')
            best_dia_idx = -1
            
            # 시간상 가장 가까운 화자 구간 찾기
            for i, ts in enumerate(dia_timestamps):
                if ts['start'] <= w_mid <= ts['end']:
                    best_label = labels[i]
                    best_dia_idx = i
                    break
                else:
                    dist = min(abs(w_mid - ts['start']), abs(w_mid - ts['end']))
                    if dist < min_dist and dist < max_offset:
                        min_dist = dist
                        best_label = labels[i]
                        best_dia_idx = i
            
            seg["speaker"] = f"Speaker {best_label}" if best_label != -1 else "Unknown"
            if best_dia_idx != -1:
                dia_texts[best_dia_idx] = seg["text"][:50] + ("..." if len(seg["text"]) > 50 else "")

        # 저장
        base_name = os.path.splitext(os.path.basename(audio_path))[0]



        final_json_path = os.path.join(output_dir, f"{base_name}.json")
        final_txt_path = os.path.join(output_dir, f"{base_name}.txt")
        
        # 중앙 DB 폴더에 군집화 데이터 저장
        db_dir = r"c:\ameva\AMEVA-STT-Agent\db\clusters"
        os.makedirs(db_dir, exist_ok=True)
        final_cluster_path = os.path.join(db_dir, f"{base_name}_clusters.json")
        
        with open(final_json_path, "w", encoding="utf-8") as f:
            json.dump(stt_data, f, indent=4, ensure_ascii=False)
            
        with open(final_txt_path, "w", encoding="utf-8") as f:
            for s in stt_data:
                f.write(f"[{s['start']:.2f} - {s['end']:.2f}] {s['speaker']}: {s['text']}\n")

        # 군집화 데이터 저장 (시각화 복원용 DB)
        cluster_data = {
            "embeddings": pca_coords,
            "labels": labels,
            "texts": dia_texts, # 호버 텍스트 추가 저장
            "original_file": audio_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(final_cluster_path, "w", encoding="utf-8") as f:
            json.dump(cluster_data, f)
                
        log(f"[Pipeline] DB 동기화 완료: {os.path.basename(final_cluster_path)}")
        
        # GUI 렌더링용 데이터 및 DB 경로 반환
        return final_json_path, np.array(pca_coords), labels, final_cluster_path, dia_texts
