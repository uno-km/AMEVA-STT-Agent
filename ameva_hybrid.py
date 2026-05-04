import sys
# 안드로이드(Termux) 환경에서의 OS 플랫폼 검증 우회
sys.platform = 'linux'

import os
import wave
import json
import math
import subprocess
import time
import argparse
import random
import csv
from datetime import datetime
from vosk import Model, SpkModel, KaldiRecognizer
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# ==========================================
# 1. 시스템 환경 설정 (Configuration)
# ==========================================
# 1) 오디오 파일 (stt_benchmark 폴더에 있음)
AUDIO_FILE = "/data/data/com.termux/files/home/projects/stt_benchmark/samples/test_cut_2.wav"

# 2) Whisper 실행 파일 (build/bin 경로 반영 완료!)
WHISPER_CMD = "/data/data/com.termux/files/home/projects/whisper.cpp/build/bin/whisper-cli"

# 3) Whisper 모델 파일
WHISPER_MODEL_SMALL = "/data/data/com.termux/files/home/projects/whisper.cpp/models/ggml-small.bin"
WHISPER_MODEL_MEDIUM = "/data/data/com.termux/files/home/projects/whisper.cpp/models/ggml-medium.bin"
# ==========================================
# 2. 순수 파이썬 기반 수학 연산 (Vector Operations)
# ==========================================
def cosine_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0: return 0.0
    return dot_product / (mag1 * mag2)

def compute_mean_vector(vectors):
    return [sum(col) / len(col) for col in zip(*vectors)]

def kmeans_clustering_k(vectors, k=2, max_iter=10):
    if not vectors:
        return [], []
    num_vectors = len(vectors)
    
    if num_vectors <= k:
        labels = list(range(num_vectors))
        centroids = vectors.copy()
        while len(centroids) < k:
            centroids.append(vectors[0])
        return labels, centroids

    centroids = random.sample(vectors, k)
    labels = []
    
    for _ in range(max_iter):
        labels = []
        clusters = {i: [] for i in range(k)}
        
        for v in vectors:
            similarities = [cosine_similarity(v, c) for c in centroids]
            best_cluster_idx = similarities.index(max(similarities))
            
            labels.append(best_cluster_idx)
            clusters[best_cluster_idx].append(v)
            
        for i in range(k):
            if clusters[i]:
                centroids[i] = compute_mean_vector(clusters[i])
                
    return labels, centroids


def pca_2d(vectors):
    if not vectors:
        return [], None
    try:
        import numpy as np
        X = np.array(vectors, dtype=float)
        mean = X.mean(axis=0)
        Xc = X - mean
        u, s, vt = np.linalg.svd(Xc, full_matrices=False)
        components = vt[:2]
        coords = (Xc @ components.T).tolist()
        return coords, {"mean": mean.tolist(), "components": components.tolist()}
    except Exception:
        dim = len(vectors[0])
        n = len(vectors)
        mean = [sum(v[i] for v in vectors) / n for i in range(dim)]
        data = [[v[i] - mean[i] for i in range(dim)] for v in vectors]
        cov = [[0.0] * dim for _ in range(dim)]
        denom = max(n - 1, 1)
        for i in range(dim):
            for j in range(i, dim):
                s = sum(row[i] * row[j] for row in data) / denom
                cov[i][j] = s
                cov[j][i] = s

        def matvec(mat, vec):
            return [sum(mat[i][j] * vec[j] for j in range(dim)) for i in range(dim)]

        def norm(vec):
            return math.sqrt(sum(x * x for x in vec))

        def power_iteration(matrix):
            vec = [random.random() for _ in range(dim)]
            length = norm(vec)
            if length == 0:
                vec = [1.0] + [0.0] * (dim - 1)
            else:
                vec = [x / length for x in vec]
            for _ in range(40):
                mv = matvec(matrix, vec)
                norm_mv = norm(mv)
                if norm_mv == 0:
                    break
                vec = [x / norm_mv for x in mv]
            eigenvalue = sum(vec[i] * matvec(matrix, vec)[i] for i in range(dim))
            return vec, eigenvalue

        v1, lam1 = power_iteration(cov)
        for i in range(dim):
            for j in range(dim):
                cov[i][j] -= lam1 * v1[i] * v1[j]
        v2, _ = power_iteration(cov)
        coords = []
        for row in data:
            x = sum(row[i] * v1[i] for i in range(dim))
            y = sum(row[i] * v2[i] for i in range(dim))
            coords.append([x, y])
        return coords, {"mean": mean, "components": [v1, v2]}


def project_vectors(vectors, transform):
    if not vectors or transform is None:
        return []
    mean = transform["mean"]
    comps = transform["components"]
    return [[sum((vec[i] - mean[i]) * comps[j][i] for i in range(len(vec))) for j in range(2)] for vec in vectors]


def create_output_prefix(base_name, args, model_name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    return f"{base_name}_{ts}_sp{args.speakers}_mo{args.max_offset}_{model_name}"


def write_csv_log(whisper_segments, csv_path):
    fieldnames = ["start", "end", "speaker_id", "matched", "time_offset", "confidence", "text"]
    with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for seg in whisper_segments:
            writer.writerow({
                "start": seg.get("start", ""),
                "end": seg.get("end", ""),
                "speaker_id": seg.get("speaker_id", "Unknown"),
                "matched": bool(seg.get("matched", False)),
                "time_offset": seg.get("time_offset", ""),
                "confidence": round(seg.get("confidence", 0.0), 4),
                "text": seg.get("text", "").replace("\n", " ")
            })


def save_visualization(whisper_segments, vosk_speakers, pca_coords, centroid_coords, output_prefix="ameva_result"):
    # Build speaker id list (exclude unknown -1)
    speaker_ids = sorted({v.get('speaker_id', -1) for v in vosk_speakers if v.get('speaker_id', -1) != -1})
    if not speaker_ids:
        speaker_ids = [0]

    id_to_y = {sid: i for i, sid in enumerate(speaker_ids)}
    unknown_y = len(speaker_ids)

    fig, ax = plt.subplots(figsize=(12, 2 + len(speaker_ids)))
    cmap = plt.get_cmap('tab10')

    # Plot Vosk speaker segments as horizontal bars
    for v in vosk_speakers:
        sid = v.get('speaker_id', -1)
        y = id_to_y.get(sid, unknown_y)
        start = v.get('start', 0)
        end = v.get('end', start)
        width = max(0.001, end - start)
        color = cmap(sid % 10) if sid != -1 else 'gray'
        rect = patches.Rectangle((start, y - 0.3), width, 0.6, facecolor=color, alpha=0.6, edgecolor='k')
        ax.add_patch(rect)

    # Plot Whisper segments as text labels positioned at matched speaker row
    for w in whisper_segments:
        sid = w.get('speaker_id', -1)
        y = id_to_y.get(sid, unknown_y)
        x = (w['start'] + w['end']) / 2.0
        txt = w.get('text', '')
        ax.text(x, y, txt if len(txt) < 120 else txt[:117] + '...', ha='center', va='center', fontsize=8, wrap=True)

    # Configure axes
    max_time = 0.0
    if vosk_speakers:
        max_time = max(max_time, max(v.get('end', 0) for v in vosk_speakers))
    if whisper_segments:
        max_time = max(max_time, max(w.get('end', 0) for w in whisper_segments))

    ax.set_xlim(0, max_time + 0.5)
    ax.set_ylim(-1, len(speaker_ids) + 0.5)
    y_ticks = list(range(len(speaker_ids)))
    ax.set_yticks(y_ticks + [unknown_y])
    ax.set_yticklabels([f"Speaker {s}" for s in speaker_ids] + ["Unknown"])
    ax.set_xlabel('Time (s)')
    ax.set_title('Speaker Diarization and Transcript Mapping')
    plt.tight_layout()

    jpg_path = f"{output_prefix}.jpg"
    fig.savefig(jpg_path, dpi=150)
    plt.close(fig)

    # Save JSON result for inspection
    json_path = f"{output_prefix}.json"
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump({"whisper_segments": whisper_segments, "vosk_speakers": vosk_speakers}, jf, ensure_ascii=False, indent=2)

    print(f"[OUTPUT] Saved visualization: {jpg_path}")
    print(f"[OUTPUT] Saved JSON result: {json_path}")

# ==========================================
# 3. 메인 프로세스 (Main Execution)
# ==========================================
def main():
    # CLI 파라미터(Args) 설정
    parser = argparse.ArgumentParser(description="AMEVA Hybrid STT Engine (Whisper + Vosk)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--small", action="store_true", help="Small 모델 사용 (기본값)")
    group.add_argument("--medium", action="store_true", help="Medium 모델 사용")
    
    # [핵심] 사용자가 입력 안 하면 알아서 기본값(default) 적용
    parser.add_argument("--speakers", type=int, default=2, help="오디오 내 예상 화자 수 지정 (기본값: 2)")
    parser.add_argument("--max_offset", type=float, default=3.0, help="매핑 허용 최대 오차 시간(초) (기본값: 3.0)")
    parser.add_argument("--output", type=str, default="ameva_result", help="결과 출력 파일 접두사 (예: ameva_result)")
    parser.add_argument("-ko", "--ko", dest="ko", action="store_true", help="한국어(Korean) 위스퍼 모드 발동 (-l ko)")
    
    args = parser.parse_args()

    # 모델 라우팅 로직
    if args.medium:
        active_whisper_model = WHISPER_MODEL_MEDIUM
        model_name = "Medium"
    else:
        active_whisper_model = WHISPER_MODEL_SMALL
        model_name = "Small"

    print("[SYSTEM] AMEVA Hybrid STT Engine 프로세스 시작")
    print(f"[SYSTEM] 대상 오디오: {AUDIO_FILE}")
    print(f"[SYSTEM] 적용 모델: Whisper {model_name}")
    print(f"[SYSTEM] 설정된 화자 수: {args.speakers}명 / 허용 오차: {args.max_offset}초")
    
    total_start_time = time.time()

    # ------------------------------------------
    # Phase 1: Whisper.cpp Transcription
    # ------------------------------------------
    print("\n[Phase 1] Whisper.cpp 전사 작업 수행 중...")
    phase1_start = time.time()
    
    # 1. 실행 명령어 리스트 구성
    whisper_args = [
        WHISPER_CMD, 
        "-m", active_whisper_model, 
        "-f", AUDIO_FILE, 
        "-oj", "-nt"
    ]

    # 2. 사용자가 --ko 옵션을 넣었다면 한국어 옵션(-l ko) 추가
    if args.ko:
        whisper_args.extend(["-l", "ko"])
        print("[SYSTEM] 한국어 강제 인식 모드가 활성화되었습니다.")

    # 3. Whisper 실행
    subprocess.run(whisper_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 4. 결과 JSON 파일 경로 정의 (이 줄이 빠져서 에러가 났던 겁니다!)
    whisper_json_file = AUDIO_FILE + ".json"

    if not os.path.exists(whisper_json_file):
        print("[ERROR] Whisper JSON 결과물을 찾을 수 없습니다. 경로를 확인하세요.")
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
            
    os.remove(whisper_json_file)
    phase1_end = time.time()
    print(f"[Phase 1] 완료 (소요 시간: {phase1_end - phase1_start:.2f}초)")

    # ------------------------------------------
    # Phase 2: Vosk Speaker Diarization
    # ------------------------------------------
    print("\n[Phase 2] Vosk 화자 임베딩(X-Vector) 추출 중...")
    phase2_start = time.time()
    
    try:
        model = Model("models/ko-model")
        spk_model = SpkModel("models/spk-model")
    except Exception as e:
        print(f"[ERROR] 모델 로드 실패: {e}")
        sys.exit(1)

    try:
        wf = wave.open(AUDIO_FILE, "rb")
    except FileNotFoundError:
        print(f"[ERROR] 오디오 파일 탐색 실패: {AUDIO_FILE}")
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
    print(f"[Phase 2] 완료 (소요 시간: {phase2_end - phase2_start:.2f}초)")

    # ------------------------------------------
    # Phase 3: Timeline Synchronization & K-Means Clustering
    # ------------------------------------------
    print("\n[Phase 3] 시계열 동기화 및 K-Means 화자 군집화 수행 중...")
    phase3_start = time.time()

    all_vectors = [v['vector'] for v in vosk_speakers]
    cluster_labels = kmeans_clustering_k(all_vectors, k=args.speakers)

    for i, v_seg in enumerate(vosk_speakers):
        v_seg['speaker_id'] = cluster_labels[i]

    print("\n============================================================")
    print("[결과] AMEVA 하이브리드 STT 출력 파이프라인")
    print("============================================================")

    for w_seg in whisper_segments:
        w_mid = (w_seg['start'] + w_seg['end']) / 2.0
        
        matched_speaker_id = -1
        current_min_diff = float('inf')
        
        for v_seg in vosk_speakers:
            v_mid = (v_seg['start'] + v_seg['end']) / 2.0
            time_diff = abs(w_mid - v_mid)
            
            # 조건 1: 시간 구간에 완벽히 포함되는 경우
            if v_seg['start'] <= w_mid <= v_seg['end']:
                matched_speaker_id = v_seg['speaker_id']
                break
                
            # 조건 2: 겹치지는 않지만, args.max_offset 이내에서 가장 가까운 경우
            elif time_diff <= args.max_offset and time_diff < current_min_diff:
                current_min_diff = time_diff
                matched_speaker_id = v_seg['speaker_id']
        
        # 매핑 실패 방어 로직 적용
        w_seg['speaker_id'] = matched_speaker_id
        speaker_label = f"Speaker {matched_speaker_id}" if matched_speaker_id != -1 else "Unknown"
        print(f"[{w_seg['start']:>5.1f}s - {w_seg['end']:>5.1f}s] [{speaker_label}] : {w_seg['text']}")

    print("============================================================")
    
    phase3_end = time.time()
    total_end_time = time.time()
    # 저장: 시각화(JPG) 및 JSON 결과
    try:
        save_visualization(whisper_segments, vosk_speakers, output_prefix=args.output)
    except Exception as e:
        print(f"[WARN] 시각화 저장 중 오류: {e}")
    
    print(f"\n[성능 프로파일링] 프로세스 실행 시간 요약")
    print(f"  - Phase 1 (Whisper ASR) : {phase1_end - phase1_start:.2f} sec")
    print(f"  - Phase 2 (Vosk Spk)    : {phase2_end - phase2_start:.2f} sec")
    print(f"  - Phase 3 (Clustering)  : {phase3_end - phase3_start:.2f} sec")
    print(f"  - 총 소요 시간          : {total_end_time - total_start_time:.2f} sec")

if __name__ == "__main__":
    main()