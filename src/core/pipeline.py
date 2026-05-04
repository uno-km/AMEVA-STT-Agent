import multiprocessing
import os
import time
import json
import numpy as np
import subprocess
from pywhispercpp.model import Model
from src.core.settings_manager import settings_manager

# --- 독립적인 병렬 워커 함수들 (Multiprocessing을 위해 최상단 레벨에 정의) ---

def worker_stt(audio_path, model_size, language, threads, output_queue):
    """
    GGML (whisper.cpp) 전사 워커 (CPU 전용, 멀티프로세스)
    """
    output_queue.put(("log", f"[STT Worker] GGML 엔진 시작: 모델({model_size}), 언어({language})"))
    start = time.time()
    
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
        
        # 모델 로드 (파일이 없으면 pywhispercpp가 자동 다운로드 시도 - 이때는 최적화된 q5_0로 받음)
        if not model_path:
            output_queue.put(("log", f"[STT Worker] 유효한 모델 파일 없음. 신규 다운로드 시도: {base_filename}"))
            # pywhispercpp 내장 다운로더는 기본 이름을 쓰므로, 
            # 가급적 아까 만든 [📥 다운로드] 버튼 사용을 권장하는 로그 출력
            model = Model(model_size, models_dir=model_dir, n_threads=threads)
        else:
            output_queue.put(("log", f"[STT Worker] 모델 로드 성공: {os.path.basename(model_path)}"))
            model = Model(model_path, n_threads=threads)
            
        # 전사 실행 (language="ko" 등)
        segments = model.transcribe(audio_path, language=language if language != "auto" else None)
        
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
    Vosk 화자 성문 벡터 추출 워커 (CPU 전용, 멀티프로세스)
    """
    output_queue.put(("log", f"[Diarization Worker] 화자 벡터 추출 시작"))
    start = time.time()
    
    # 향후 실제 Vosk KaldiRecognizer + SpkModel 로직을 여기에 연동합니다.
    # 현재는 뼈대 구조이므로 처리 시간을 모사하고 Mock 벡터를 반환합니다.
    time.sleep(3.5) 
    
    # Mock 데이터 (타임스탬프, 화자 임베딩 벡터 2차원)
    # 실제로는 128차원 x벡터를 뽑아내야 하지만 GUI 데모를 위해 2차원 난수로 모사
    mock_vectors = np.random.rand(20, 2).tolist()
    mock_labels = [i % 2 for i in range(20)] # Speaker 0, 1
    
    elapsed = time.time() - start
    output_queue.put(("log", f"[Diarization Worker] 완료 ({elapsed:.1f}초)"))
    output_queue.put(("dia_result", (mock_vectors, mock_labels)))

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

    def execute(self, audio_path, output_dir, logger_callback=None):
        """
        Multiprocessing을 통해 STT와 Diarization을 병렬로 돌리고 Phase 3에서 병합합니다.
        """
        def log(msg):
            if logger_callback: logger_callback(msg)
            
        log(f"[Pipeline] 파일 병렬 분석 준비 중: {audio_path}")
        
        # Phase 0: 오디오 전처리 (WAV 변환)
        processed_audio = self.convert_to_wav(audio_path, log)
        
        # 설정 불러오기
        stt_config = settings_manager.get("stt")
        model_size = stt_config.get("model", "medium").split()[0] # "turbo (v3)" -> "turbo"
        language = stt_config.get("language", "ko")
        threads = int(stt_config.get("threads", 4))

        # 통신용 큐 생성
        manager = multiprocessing.Manager()
        q = manager.Queue()
        
        # 프로세스 생성
        p_stt = multiprocessing.Process(target=worker_stt, args=(processed_audio, model_size, language, threads, q))
        p_dia = multiprocessing.Process(target=worker_diarization, args=(processed_audio, q))
        
        # 동시 시작
        p_stt.start()
        p_dia.start()
        
        # 큐에서 실시간 로그 및 결과 스트리밍
        stt_data = []
        dia_vectors, dia_labels = [], []
        finished_procs = 0
        
        while finished_procs < 2:
            key, val = q.get()
            if key == "log":
                log(val)
            elif key == "stt_result":
                stt_data = val
                finished_procs += 1
            elif key == "dia_result":
                dia_vectors, dia_labels = val
                finished_procs += 1
                
        p_stt.join()
        p_dia.join()
        
        log(f"[Pipeline] Phase 1, 2 완료. K-Means 군집화 및 텍스트 매핑 시작...")
        
        # Phase 3: 클러스터링 및 병합 모사 로직
        for i, seg in enumerate(stt_data):
            # 화자를 교차로 할당 모사
            seg["speaker"] = f"Speaker {i % 2}"
            
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
            "embeddings": dia_vectors.tolist() if isinstance(dia_vectors, np.ndarray) else dia_vectors,
            "labels": dia_labels,
            "original_file": audio_path,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(final_cluster_path, "w", encoding="utf-8") as f:
            json.dump(cluster_data, f)
                
        log(f"[Pipeline] DB 동기화 완료: {os.path.basename(final_cluster_path)}")
        
        # GUI 렌더링용 데이터 및 DB 경로 반환
        return final_json_path, np.array(dia_vectors), dia_labels, final_cluster_path
