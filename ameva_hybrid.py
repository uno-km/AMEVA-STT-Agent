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
from matplotlib.lines import Line2D

SCRIPT_VERSION = "v1.4"
SCRIPT_MODIFIED = "2026-05-04"

# ==========================================
# 지능형 환경 진단 및 데이터 사이언스 모듈 (Intelligent Environment Diagnosis & Data Science Module)
# ==========================================
class EnvironmentManager:
    def __init__(self):
        self.home = os.path.expanduser("~")
        self.projects_dir = os.path.join(self.home, "projects")
        self.current_dir = os.getcwd()
        
        # 탐색된 경로들
        self.whisper_cmd = None
        self.whisper_model_small = None
        self.whisper_model_medium = None
        self.libvosk_path = None
        self.audio_file = None
        
        # 초기화 실행
        self._discover_paths()
        self._check_dependencies()
    
    def _discover_paths(self):
        print("[INIT] 환경 자동 탐색 중...")
        
        # 1. Whisper 실행 파일 탐색
        self._find_whisper_executable()
        
        # 2. Whisper 모델 파일 탐색
        self._find_whisper_models()
        
        # 3. Vosk 라이브러리 탐색
        self._find_libvosk()
        
        # 4. 오디오 파일 탐색
        self._find_audio_file()
        
        print("[INIT] 환경 탐색 완료")
    
    def _find_whisper_executable(self):
        candidates = ["whisper-cli", "main"]
        search_paths = [
            self.projects_dir,
            os.path.join(self.projects_dir, "whisper.cpp"),
            os.path.join(self.projects_dir, "whisper.cpp", "build"),
            os.path.join(self.projects_dir, "whisper.cpp", "build", "bin")
        ]
        
        # ~/projects 하위 모든 폴더 검색
        for root, dirs, files in os.walk(self.projects_dir):
            for candidate in candidates:
                if candidate in files:
                    full_path = os.path.join(root, candidate)
                    if os.access(full_path, os.X_OK):
                        self.whisper_cmd = full_path
                        print(f"[INIT] Whisper 실행 파일 발견: {self.whisper_cmd}")
                        return
        
        # $HOME 전체 검색
        print("[INIT] ~/projects에서 Whisper 실행 파일을 찾지 못했습니다. $HOME 전체 검색 중...")
        for root, dirs, files in os.walk(self.home):
            for candidate in candidates:
                if candidate in files:
                    full_path = os.path.join(root, candidate)
                    if os.access(full_path, os.X_OK):
                        self.whisper_cmd = full_path
                        print(f"[INIT] Whisper 실행 파일 발견: {self.whisper_cmd}")
                        return
        
        print("[WARN] Whisper 엔진이 빌드되지 않았습니다. whisper.cpp를 빌드해주세요.")
        self.whisper_cmd = None
    
    def _find_whisper_models(self):
        model_names = ["ggml-small.bin", "ggml-medium.bin"]
        search_paths = [
            os.path.join(self.projects_dir, "whisper.cpp", "models"),
            os.path.join(self.home, "models"),
            self.current_dir
        ]
        
        for model_name in model_names:
            for path in search_paths:
                full_path = os.path.join(path, model_name)
                if os.path.isfile(full_path):
                    if "small" in model_name:
                        self.whisper_model_small = full_path
                    else:
                        self.whisper_model_medium = full_path
                    print(f"[INIT] Whisper 모델 발견: {full_path}")
                    break
        
        # 모델이 없으면 다운로드 제안
        if not self.whisper_model_small or not self.whisper_model_medium:
            self._offer_model_download()
    
    def _find_libvosk(self):
        lib_candidates = ["libvosk.so", "libvosk.dylib", "vosk.dll"]
        search_paths = [
            "/usr/lib",
            "/usr/local/lib",
            os.path.join(self.home, ".local", "lib"),
            self.projects_dir
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                for root, dirs, files in os.walk(path):
                    for lib in lib_candidates:
                        if lib in files:
                            self.libvosk_path = os.path.join(root, lib)
                            print(f"[INIT] Vosk 라이브러리 발견: {self.libvosk_path}")
                            return
        
        print("[WARN] libvosk.so를 찾지 못했습니다. 설치가 필요할 수 있습니다.")
        self.libvosk_path = None
    
    def _offer_model_download(self):
        print("[INIT] 일부 Whisper 모델이 없습니다.")
        response = input("모델을 다운로드할까요? (y/n): ").strip().lower()
        if response == 'y':
            self._download_models()
        else:
            print("[INIT] 모델 다운로드를 건너뜁니다.")
    
    def _download_models(self):
        models_dir = os.path.join(self.projects_dir, "whisper.cpp", "models")
        os.makedirs(models_dir, exist_ok=True)
        
        # download-ggml-model.sh 스크립트 사용 시도
        script_path = os.path.join(self.projects_dir, "whisper.cpp", "models", "download-ggml-model.sh")
        if os.path.isfile(script_path):
            print("[INIT] download-ggml-model.sh를 사용하여 모델 다운로드 중...")
            try:
                subprocess.run([script_path, "small"], check=True)
                subprocess.run([script_path, "medium"], check=True)
                self._find_whisper_models()  # 재탐색
                return
            except subprocess.CalledProcessError:
                print("[WARN] download-ggml-model.sh 실행 실패. 직접 다운로드 시도.")
        
        # 직접 curl 다운로드
        base_url = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
        models = {
            "ggml-small.bin": "ggml-small.bin",
            "ggml-medium.bin": "ggml-medium.bin"
        }
        
        for model_name, filename in models.items():
            url = f"{base_url}/{filename}"
            output_path = os.path.join(models_dir, model_name)
            print(f"[INIT] 다운로드 중: {url} -> {output_path}")
            try:
                subprocess.run(["curl", "-L", url, "-o", output_path], check=True)
                if "small" in model_name:
                    self.whisper_model_small = output_path
                else:
                    self.whisper_model_medium = output_path
            except subprocess.CalledProcessError:
                print(f"[ERROR] {model_name} 다운로드 실패")
    
    def _find_audio_file(self):
        # 기본 오디오 파일 경로 시도
        default_audio = "/data/data/com.termux/files/home/projects/stt_benchmark/samples/test_cut_2.wav"
        if os.path.isfile(default_audio):
            self.audio_file = default_audio
            print(f"[INIT] 기본 오디오 파일 발견: {self.audio_file}")
            return
        
        # 현재 디렉토리에서 .wav 파일 검색 및 선택
        wav_files = [f for f in os.listdir(self.current_dir) if f.endswith('.wav')]
        if wav_files:
            print("[INIT] 현재 디렉토리의 .wav 파일들:")
            for i, f in enumerate(wav_files):
                print(f"  {i+1}. {f}")
            try:
                choice = input("사용할 오디오 파일 번호를 입력하세요 (또는 직접 경로 입력): ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(wav_files):
                        self.audio_file = os.path.join(self.current_dir, wav_files[idx])
                    else:
                        self.audio_file = choice
                else:
                    self.audio_file = choice
            except ValueError:
                self.audio_file = input("오디오 파일 경로를 입력하세요: ").strip()
        else:
            self.audio_file = input("오디오 파일 경로를 입력하세요: ").strip()
        
        if not os.path.isfile(self.audio_file):
            print(f"[ERROR] 오디오 파일을 찾을 수 없습니다: {self.audio_file}")
            self.audio_file = None
    
    def _check_dependencies(self):
        print("[INIT] 의존성 확인 중...")
        
        # Vosk 체크
        try:
            import vosk
            print("[INIT] Vosk 라이브러리 확인됨")
        except ImportError:
            print("[WARN] Vosk 라이브러리가 설치되지 않았습니다.")
            self._offer_install("vosk")
        
        # Matplotlib 체크
        try:
            import matplotlib
            print("[INIT] Matplotlib 라이브러리 확인됨")
        except ImportError:
            print("[WARN] Matplotlib 라이브러리가 설치되지 않았습니다.")
            self._offer_install("matplotlib")
        
        # Numpy 체크 (선택적)
        try:
            import numpy
            print("[INIT] Numpy 라이브러리 확인됨")
        except ImportError:
            print("[INFO] Numpy 라이브러리가 설치되지 않았습니다. (선택적)")
    
    def _offer_install(self, package):
        response = input(f"{package}를 설치할까요? (y/n): ").strip().lower()
        if response == 'y':
            try:
                if package == "vosk":
                    # Termux에서는 apt 사용
                    if os.path.exists("/data/data/com.termux"):
                        subprocess.run(["pkg", "install", "vosk-api", "-y"], check=True)
                    else:
                        subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
                else:
                    subprocess.run([sys.executable, "-m", "pip", "install", package], check=True)
                print(f"[INIT] {package} 설치 완료")
            except subprocess.CalledProcessError:
                print(f"[ERROR] {package} 설치 실패")
        else:
            print(f"[INIT] {package} 설치를 건너뜁니다.")

# ==========================================
# 1. 시스템 환경 설정 (Configuration) - 이제 EnvironmentManager에서 관리
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


def create_output_prefix(base_name, args, model_name, audio_file):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    audio_basename = os.path.basename(audio_file)
    speakers_param = f"sp{args.speakers}"
    offset_param = f"mo{args.max_offset}"
    ko_param = "_ko" if args.ko else ""
    return f"{base_name}_{ts}_{speakers_param}_{offset_param}_{model_name}{ko_param}_{audio_basename}"


def setup_matplotlib_fonts():
    """한글 폰트 설정 및 예외 처리"""
    try:
        import matplotlib.font_manager as fm
        # 시스템 폰트 찾기
        font_list = fm.findSystemFonts()
        korean_fonts = [f for f in font_list if 'nanum' in f.lower() or 'malgun' in f.lower() or 'gulim' in f.lower()]
        
        if korean_fonts:
            plt.rcParams['font.family'] = 'NanumGothic' if 'nanum' in korean_fonts[0].lower() else 'Malgun Gothic'
            print("[FONT] 한글 폰트 설정됨")
        else:
            plt.rcParams['font.family'] = 'DejaVu Sans'
            print("[FONT] 한글 폰트가 없어 영문 폰트로 대체합니다")
    except Exception as e:
        plt.rcParams['font.family'] = 'DejaVu Sans'
        print(f"[FONT] 폰트 설정 중 오류: {e}, 영문 폰트 사용")


def write_csv_log(whisper_segments, csv_path, env_manager=None, args=None, model_name="", total_time=0.0, success_rate=0.0):
    with open(csv_path, "w", encoding="utf-8", newline="") as csvfile:
        # 메타데이터 주석 추가
        csvfile.write(f"# AMEVA Hybrid STT Result\n")
        csvfile.write(f"# Timestamp: {datetime.now().isoformat()}\n")
        csvfile.write(f"# Audio File: {env_manager.audio_file if env_manager else 'unknown'}\n")
        csvfile.write(f"# Model: {model_name}\n")
        csvfile.write(f"# Speakers: {args.speakers if args else 2}\n")
        csvfile.write(f"# Max Offset: {args.max_offset if args else 3.0}\n")
        csvfile.write(f"# Korean Mode: {args.ko if args else False}\n")
        csvfile.write(f"# Execution Time: {total_time:.2f}s\n")
        csvfile.write(f"# Success Rate: {success_rate:.2f}%\n")
        csvfile.write("\n")  # 빈 줄
        
        fieldnames = ["start", "end", "speaker_id", "matched", "time_offset", "cosine_similarity", "text"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for seg in whisper_segments:
            writer.writerow({
                "start": seg.get("start", ""),
                "end": seg.get("end", ""),
                "speaker_id": seg.get("speaker_id", "Unknown"),
                "matched": bool(seg.get("matched", False)),
                "time_offset": seg.get("time_offset", ""),
                "cosine_similarity": round(seg.get("confidence", 0.0), 4),
                "text": seg.get("text", "").replace("\n", " ")
            })


def save_visualization(whisper_segments, vosk_speakers, pca_coords, centroid_coords, output_prefix="ameva_result", env_manager=None, args=None, model_name="", total_time=0.0, success_rate=0.0):
    # 한글 폰트 설정
    setup_matplotlib_fonts()
    
    speaker_ids = sorted({v.get('speaker_id', -1) for v in vosk_speakers if v.get('speaker_id', -1) != -1})
    if not speaker_ids:
        speaker_ids = [0]

    id_to_y = {sid: i for i, sid in enumerate(speaker_ids)}
    unknown_y = len(speaker_ids)
    cmap = plt.get_cmap('tab10')

    fig, (ax_time, ax_scatter) = plt.subplots(2, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [1, 1]})

    # Timeline visualization
    for v in vosk_speakers:
        sid = v.get('speaker_id', -1)
        y = id_to_y.get(sid, unknown_y)
        start = v.get('start', 0)
        end = v.get('end', start)
        width = max(0.001, end - start)
        color = cmap(sid % 10) if sid != -1 else 'gray'
        rect = patches.Rectangle((start, y - 0.3), width, 0.6, facecolor=color, alpha=0.6, edgecolor='k')
        ax_time.add_patch(rect)

    for w in whisper_segments:
        sid = w.get('speaker_id', -1)
        y = id_to_y.get(sid, unknown_y)
        x = (w['start'] + w['end']) / 2.0
        txt = w.get('text', '')
        annotation = txt if len(txt) < 80 else txt[:77] + '...'
        color = 'black' if w.get('matched', False) else 'red'
        marker = 'o' if w.get('matched', False) else 'x'
        ax_time.scatter([x], [y], marker=marker, c=color, s=30)
        ax_time.text(x, y + 0.35, annotation, ha='center', va='bottom', fontsize=7, color=color, wrap=True)

    max_time = 0.0
    if vosk_speakers:
        max_time = max(max_time, max(v.get('end', 0) for v in vosk_speakers))
    if whisper_segments:
        max_time = max(max_time, max(w.get('end', 0) for w in whisper_segments))

    ax_time.set_xlim(0, max_time + 0.5)
    ax_time.set_ylim(-1, len(speaker_ids) + 0.5)
    y_ticks = list(range(len(speaker_ids)))
    ax_time.set_yticks(y_ticks + [unknown_y])
    ax_time.set_yticklabels([f"Speaker {s}" for s in speaker_ids] + ["Unknown"])
    ax_time.set_xlabel('Time (s)')
    ax_time.set_title('Whisper-Vosk Timeline and Mapping')
    ax_time.grid(axis='x', alpha=0.3)

    # PCA scatter visualization
    if pca_coords:
        xs = [coord[0] for coord in pca_coords]
        ys = [coord[1] for coord in pca_coords]
        colors = [cmap(v.get('speaker_id', -1) % 10) if v.get('speaker_id', -1) != -1 else 'gray' for v in vosk_speakers]
        ax_scatter.scatter(xs, ys, c=colors, s=70, edgecolors='k', alpha=0.8)

        for idx, (x, y) in enumerate(pca_coords):
            ax_scatter.text(x, y, str(idx), fontsize=8, ha='center', va='center')

        for sid, coord in centroid_coords.items():
            ax_scatter.scatter(coord[0], coord[1], marker='X', s=180, c=cmap(sid % 10), edgecolors='black')
            ax_scatter.text(coord[0], coord[1], f'C{sid}', fontsize=10, weight='bold', ha='center', va='center')

        for i, w in enumerate(whisper_segments):
            mapped_idx = w.get('mapped_vosk_index', -1)
            if 0 <= mapped_idx < len(pca_coords):
                px, py = pca_coords[mapped_idx]
                label = f"{i}:{w.get('text','')[:24]}"
                offset = 0.12 if i % 2 == 0 else -0.12
                if w.get('matched', False):
                    ax_scatter.annotate(label, xy=(px, py), xytext=(px + 0.25, py + offset), arrowprops={'arrowstyle': '->', 'color': 'black', 'alpha': 0.7}, fontsize=7)
                else:
                    ax_scatter.scatter([px], [py], marker='X', c='red', s=120, edgecolors='k')
                    ax_scatter.annotate(label + ' (Unknown)', xy=(px, py), xytext=(px + 0.25, py + offset), arrowprops={'arrowstyle': '-|>', 'color': 'red', 'alpha': 0.7, 'linestyle': 'dashed'}, fontsize=7, color='red')

        legend_handles = []
        for sid in speaker_ids:
            legend_handles.append(patches.Patch(color=cmap(sid % 10), label=f'Speaker {sid}'))
        legend_handles.append(plt.Line2D([0], [0], marker='X', color='w', label='Centroid', markerfacecolor='black', markersize=10))
        legend_handles.append(plt.Line2D([0], [0], marker='x', color='red', label='Unknown', markersize=8))
        ax_scatter.legend(handles=legend_handles, loc='best', fontsize=8)
        ax_scatter.set_title('Vosk X-Vector PCA Scatter with Speaker Clusters')
        ax_scatter.set_xlabel('PCA Component 1')
        ax_scatter.set_ylabel('PCA Component 2')
        ax_scatter.grid(alpha=0.3)
    else:
        ax_scatter.text(0.5, 0.5, 'PCA unavailable: no Vosk vectors', ha='center', va='center', fontsize=12)
        ax_scatter.axis('off')

    fig.tight_layout()
    jpg_path = f"{output_prefix}.jpg"
    fig.savefig(jpg_path, dpi=150)
    plt.close(fig)

    json_path = f"{output_prefix}.json"
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump({
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "audio_file": env_manager.audio_file if env_manager else "unknown",
                "model": model_name,
                "speakers": args.speakers if args else 2,
                "max_offset": args.max_offset if args else 3.0,
                "korean_mode": args.ko if args else False,
                "execution_time": total_time,
                "success_rate": success_rate
            },
            "whisper_segments": whisper_segments,
            "vosk_speakers": vosk_speakers,
            "centroid_coords": centroid_coords
        }, jf, ensure_ascii=False, indent=2)

    print(f"[OUTPUT] Saved visualization: {jpg_path}")
    print(f"[OUTPUT] Saved JSON result: {json_path}")


def save_meeting_minutes(whisper_segments, output_prefix):
    """회의록을 Markdown 및 텍스트로 저장합니다."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_lines = [
        "# 🎙️ 자동 생성 회의록 (AMEVA Hybrid STT)",
        f"- **생성 일시:** {now}",
        "- **사용 엔진:** Whisper (Text) + Vosk (Diarization)",
        "",
        "---",
        ""
    ]
    txt_lines = [
        "자동 생성 회의록 (AMEVA Hybrid STT)",
        f"생성 일시: {now}",
        "사용 엔진: Whisper (Text) + Vosk (Diarization)",
        "",
        "============================================================",
        ""
    ]

    prev_speaker = None
    for seg in whisper_segments:
        speaker_id = seg.get("speaker_id", -1)
        speaker_label = "Unknown" if speaker_id == -1 else f"Speaker {speaker_id}"
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = seg.get("text", "").strip()
        ts = f"[{start:05.1f}s - {end:05.1f}s]"

        if speaker_id != prev_speaker:
            md_lines.append(f"### 🗣️ {speaker_label}")
            txt_lines.append(f"{speaker_label}")
            prev_speaker = speaker_id

        md_lines.append(f"> {ts} {text}")
        txt_lines.append(f"{ts} {text}")

    md_path = f"{output_prefix}_minutes.md"
    txt_path = f"{output_prefix}_minutes.txt"

    with open(md_path, "w", encoding="utf-8") as md_file:
        md_file.write("\n".join(md_lines) + "\n")

    with open(txt_path, "w", encoding="utf-8") as txt_file:
        txt_file.write("\n".join(txt_lines) + "\n")

    return md_path, txt_path

# ==========================================
# 3. 메인 프로세스 (Main Execution)
# ==========================================
def main():
    print(f"[SYSTEM] AMEVA Hybrid STT Engine 시작 - 버전 {SCRIPT_VERSION} / 최종 수정일 {SCRIPT_MODIFIED}")

    # 환경 초기화
    env_manager = EnvironmentManager()
    
    # 필수 경로 확인
    if not env_manager.whisper_cmd:
        print("[ERROR] Whisper 실행 파일이 필요합니다.")
        sys.exit(1)
    if not env_manager.whisper_model_small and not env_manager.whisper_model_medium:
        print("[ERROR] Whisper 모델 파일이 필요합니다.")
        sys.exit(1)
    if not env_manager.audio_file:
        print("[ERROR] 오디오 파일이 필요합니다.")
        sys.exit(1)
    
    # CLI 파라미터(Args) 설정
    parser = argparse.ArgumentParser(description="AMEVA Hybrid STT Engine (Whisper + Vosk)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--small", action="store_true", help="Small 모델 사용 (기본값)")
    group.add_argument("--medium", action="store_true", help="Medium 모델 사용")
    
    # [핵심] 사용자가 입력 안 하면 알아서 기본값(default) 적용
    parser.add_argument("--speakers", type=int, default=2, help="오디오 내 예상 화자 수 지정 (기본값: 2)")
    parser.add_argument("--max_offset", type=float, default=2.0, help="매핑 허용 최대 오차 시간(초) (기본값: 2.0 - 더 엄격)")
    parser.add_argument("--output", type=str, default="ameva_result", help="결과 출력 파일 접두사 (예: ameva_result)")
    parser.add_argument("-ko", "--ko", dest="ko", action="store_true", help="한국어(Korean) 위스퍼 모드 발동 (-l ko)")
    parser.add_argument("--whisper_max_len", type=int, default=20, help="Whisper.cpp 최대 문장 길이 (문자/토큰 수 기준) - 더 짧은 분할 (기본값: 20)")
    parser.add_argument("--whisper_split_on_word", action="store_true", default=True, help="Whisper.cpp -sow 옵션: 단어 경계 기준 분리 (기본값: 활성화)")
    parser.add_argument("--whisper_no_split_on_word", dest="whisper_split_on_word", action="store_false", help="-sow 옵션 비활성화 (기본값 무시)")
    parser.add_argument("--whisper_vad", action="store_true", help="[실험] Whisper.cpp VAD 활성화 (일부 버전 미지원) - 기본값: 비활성화")
    parser.add_argument("--whisper_vad_max_speech_duration", type=int, default=5, help="VAD 최대 연속 음성 길이 (초) (기본값: 5)")
    parser.add_argument("--whisper_vad_min_silence_duration", type=int, default=500, help="VAD 최소 침묵 길이 (밀리초) (기본값: 500)")
    
    args = parser.parse_args()

    # 모델 라우팅 로직
    if args.medium:
        if not env_manager.whisper_model_medium:
            print("[ERROR] Medium 모델이 없습니다. Small 모델로 전환합니다.")
            active_whisper_model = env_manager.whisper_model_small
            model_name = "Small"
        else:
            active_whisper_model = env_manager.whisper_model_medium
            model_name = "Medium"
    else:
        if not env_manager.whisper_model_small:
            if env_manager.whisper_model_medium:
                print("[WARN] Small 모델이 없어 Medium 모델로 전환합니다.")
                active_whisper_model = env_manager.whisper_model_medium
                model_name = "Medium"
            else:
                print("[ERROR] 사용할 수 있는 모델이 없습니다.")
                sys.exit(1)
        else:
            active_whisper_model = env_manager.whisper_model_small
            model_name = "Small"

    print("[SYSTEM] AMEVA Hybrid STT Engine 프로세스 시작")
    print(f"[SYSTEM] 대상 오디오: {env_manager.audio_file}")
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
        env_manager.whisper_cmd,
        "-m", active_whisper_model,
        "-f", env_manager.audio_file,
        "-ml", str(args.whisper_max_len),  # 최대 문장 길이: 문자/토큰 기준, 시간(초) 기준 아님
        "-oj", "-nt"
    ]
    if args.whisper_split_on_word:
        whisper_args.append("-sow")  # 단어 경계 기준 분리: 더 짧은 세그먼트를 만들 수 있음
    if args.whisper_vad:
        whisper_args.extend([
            "--vad",
            "--vad-max-speech-duration-s", str(args.whisper_vad_max_speech_duration),
            "--vad-min-silence-duration-ms", str(args.whisper_vad_min_silence_duration)
        ])  # VAD 활성화: 음성/침묵 기준으로 세그먼트 분리

    # 2. 사용자가 --ko 옵션을 넣었다면 한국어 옵션(-l ko) 추가
    if args.ko:
        whisper_args.extend(["-l", "ko"])
        print("[SYSTEM] 한국어 강제 인식 모드가 활성화되었습니다.")

    # 3. Whisper 실행
    result = subprocess.run(whisper_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Whisper 실행 실패: {result.stderr}")
        sys.exit(1)

    # 4. 결과 JSON 파일 경로 정의 (이 줄이 빠져서 에러가 났던 겁니다!)
    whisper_json_file = env_manager.audio_file + ".json"

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
        wf = wave.open(env_manager.audio_file, "rb")
    except FileNotFoundError:
        print(f"[ERROR] 오디오 파일 탐색 실패: {env_manager.audio_file}")
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
    cluster_labels, centroids = kmeans_clustering_k(all_vectors, k=args.speakers)

    for i, v_seg in enumerate(vosk_speakers):
        v_seg['speaker_id'] = cluster_labels[i]

    pca_coords, pca_transform = pca_2d(all_vectors)
    centroid_coords_list = project_vectors(centroids, pca_transform)
    centroid_coords = {i: coord for i, coord in enumerate(centroid_coords_list)}

    print("\n============================================================")
    print("[결과] AMEVA 하이브리드 STT 출력 파이프라인")
    print("============================================================")

    matched_count = 0
    for w_seg in whisper_segments:
        w_mid = (w_seg['start'] + w_seg['end']) / 2.0
        
        matched_speaker_id = -1
        best_idx = -1
        nearest_time_diff = float('inf')
        matching_time_diff = float('inf')
        
        for idx, v_seg in enumerate(vosk_speakers):
            v_mid = (v_seg['start'] + v_seg['end']) / 2.0
            time_diff = abs(w_mid - v_mid)
            if time_diff < nearest_time_diff:
                nearest_time_diff = time_diff
                best_idx = idx

            if v_seg['start'] <= w_mid <= v_seg['end']:
                matched_speaker_id = v_seg['speaker_id']
                best_idx = idx
                matching_time_diff = 0.0
                break
            elif time_diff <= args.max_offset and time_diff < matching_time_diff:
                matched_speaker_id = v_seg['speaker_id']
                matching_time_diff = time_diff

        w_seg['mapped_vosk_index'] = best_idx
        w_seg['speaker_id'] = matched_speaker_id
        w_seg['time_offset'] = matching_time_diff if matching_time_diff != float('inf') else nearest_time_diff if nearest_time_diff != float('inf') else None
        w_seg['matched'] = matched_speaker_id != -1

        if best_idx != -1 and best_idx < len(vosk_speakers):
            v_seg = vosk_speakers[best_idx]
            centroid = centroids[cluster_labels[best_idx]] if centroids else v_seg['vector']
            w_seg['confidence'] = cosine_similarity(v_seg['vector'], centroid)
        else:
            w_seg['confidence'] = 0.0

        if w_seg['matched']:
            matched_count += 1

        speaker_label = f"Speaker {matched_speaker_id}" if matched_speaker_id != -1 else "Unknown"
        print(f"[{w_seg['start']:>5.1f}s - {w_seg['end']:>5.1f}s] [{speaker_label}] time_offset={w_seg['time_offset']:.3f} conf={w_seg['confidence']:.4f} : {w_seg['text']}")

    print("============================================================")

    success_rate = (matched_count / len(whisper_segments) * 100.0) if whisper_segments else 0.0
    phase3_end = time.time()
    total_end_time = time.time()

    output_prefix = create_output_prefix(args.output, args, model_name, env_manager.audio_file)
    csv_path = f"{output_prefix}.csv"
    write_csv_log(whisper_segments, csv_path, env_manager=env_manager, args=args, model_name=model_name, total_time=total_end_time - total_start_time, success_rate=success_rate)
    print(f"[OUTPUT] Saved CSV log: {csv_path}")

    try:
        save_visualization(whisper_segments, vosk_speakers, pca_coords, centroid_coords, output_prefix=output_prefix, env_manager=env_manager, args=args, model_name=model_name, total_time=total_end_time - total_start_time, success_rate=success_rate)
    except Exception as e:
        print(f"[WARN] 시각화 저장 중 오류: {e}")

    try:
        md_path, txt_path = save_meeting_minutes(whisper_segments, output_prefix)
        print(f"[OUTPUT] ✨ 회의록 자동 생성 완료: {md_path}, {txt_path}")
    except Exception as e:
        print(f"[WARN] 회의록 저장 중 오류: {e}")

    print(f"\n[성능 프로파일링] 프로세스 실행 시간 요약")
    print(f"  - Phase 1 (Whisper ASR) : {phase1_end - phase1_start:.2f} sec ({(phase1_end - phase1_start) / (total_end_time - total_start_time) * 100 if total_end_time > total_start_time else 0:.1f}%)")
    print(f"  - Phase 2 (Vosk Spk)    : {phase2_end - phase2_start:.2f} sec ({(phase2_end - phase2_start) / (total_end_time - total_start_time) * 100 if total_end_time > total_start_time else 0:.1f}%)")
    print(f"  - Phase 3 (Clustering)  : {phase3_end - phase3_start:.2f} sec ({(phase3_end - phase3_start) / (total_end_time - total_start_time) * 100 if total_end_time > total_start_time else 0:.1f}%)")
    print(f"  - 총 소요 시간          : {total_end_time - total_start_time:.2f} sec")
    print(f"  - 매핑 성공률            : {success_rate:.2f}% ({matched_count}/{len(whisper_segments)})")

if __name__ == "__main__":
    main()