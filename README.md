# AMEVA Hybrid STT: High-Fidelity Speech Transcription and Diarization Pipeline

## 핵심 기능 (Core Features)

*   **Hybrid Engine Synergy**: Whisper.cpp의 정밀한 전사 성능과 Vosk의 고속 화자 임베딩 기술을 결합하였습니다.
*   **Sequential Forced Diarization**: 시간축 기반의 확률적 매핑이 아닌, 전사 세그먼트 기준의 강제 매핑으로 화자 분류 오류를 원천 차단합니다.
*   **Interactive Analysis Dashboard**: PCA 기반의 화자 군집 시각화 차트와 실시간 로그 스트리밍을 제공합니다.
*   **Enterprise Batch Processing**: 수백 개의 오디오 파일을 자동으로 스캔하여 병렬 처리하며, 모든 이력을 데이터베이스화합니다.

---

## 1. 개요 (Abstract)

본 프로젝트는 대규모 언어 모델 기반의 음성 인식(Speech-to-Text) 기술과 화자 분리(Speaker Diarization) 기술을 결합하여, 다중 화자가 포함된 오디오 데이터를 고도로 정밀하게 텍스트화하고 분류하는 엔터프라이즈급 솔루션입니다. 

기존의 단순 시간축 정렬 방식에서 발생하는 화자 매핑 오차를 극복하기 위해 **"Sequential Forced Diarization"** 아키텍처를 채택하였으며, 멀티코어 프로세싱 가속 및 비동기 파이프라인 설계를 통해 실시간에 준하는 처리 성능과 높은 데이터 무결성을 보장합니다.

---

## 2. 시스템 아키텍처 (System Architecture)

![System Architecture](assets/architecture_diagram.png)

본 시스템은 **SSOT(Single Source of Truth) 기반 상태 관리**와 **계층화된 모듈 분리(Layered Architecture)** 원칙을 따릅니다.

### 2.1 처리 파이프라인 (Processing Pipeline)
1.  **Audio Normalization (FFmpeg)**: 입력 오디오를 16kHz Mono로 통일하여 특징 추출의 일관성을 확보합니다.
2.  **Deterministic STT (Whisper)**: GGUF 양자화 모델을 사용하여 CPU 환경에서 최적화된 텍스트 전사를 수행합니다.
3.  **Forced Embedding (Vosk)**: 확정된 STT 타임스탬프 구간의 오디오를 분석하여 화자 고유의 X-Vector를 추출합니다.
4.  **Unsupervised Clustering (K-Means)**: 추출된 벡터들을 코사인 유사도 기반으로 군집화하여 최종 화자를 결정합니다.

### 2.2 GUI 대시보드 구조 (User Interface Design)

![UI Overview](assets/ui_overview.png)

사용자 편의성을 극대화하기 위해 4분할 레이아웃 아키텍처를 적용하였습니다.

*   **Data Explorer (Left)**: 작업 디렉토리 내의 원본 오디오 및 분석된 결과 파일들을 계층적으로 관리합니다.
*   **Advanced Viewer (Center-Top)**: 분석 완료된 JSON 및 TXT 결과물을 탭 인터페이스를 통해 즉각적으로 검토합니다.
*   **Analysis & Visualization (Center-Bottom)**: 시스템/파이프라인 로그와 함께, PCA로 축소된 화자 군집 산점도를 실시간으로 모니터링합니다.
*   **Control & Configuration (Right)**: 모델 크기, 언어, 스레드 수 등의 엔진 파라미터와 배치 스케줄러를 제어합니다.

---

## 3. 디렉토리 구조 (Directory Structure)

도메인 주도 설계(DDD) 관점의 모듈화를 통해 코드 가독성과 유지보수성을 극대화했습니다.

```text
AMEVA-STT-Agent/
├── assets/             # 아키텍처 다이어그램 및 정적 자산
├── db/                 # 전역 데이터베이스 (Batch Log, Exception, Mapping)
│   └── clusters/       # 세부 군집화 데이터 및 PCA 벡터 저장소
├── docker/             # 컨테이너화 설정 (Dockerfile, Compose)
├── gui/                # PyQt6 기반 고성능 대시보드 UI
│   ├── panels/         # 개별 UI 컴포넌트 (Logging, Settings, Viewer 등)
├── output_results/     # 최종 전사 결과물 (JSON, TXT)
├── src/
│   ├── core/           # 파이프라인 오케스트레이터 및 엔진 래퍼
│   ├── diarization/    # 클러스터링 및 수학적 연산 모듈
│   └── utils/          # 비동기 워커 및 시스템 유틸리티
├── settings.json       # 싱글톤 상태 저장소
└── main.py             # 시스템 엔트리 포인트
```

---

## 4. Docker 컨테이너화 (Docker Containerization)

본 시스템은 GUI 대시보드 환경과 배치(Batch) 워커 환경의 분리를 고려하여 설계되었습니다.
- **Headless Worker**: 대용량 데이터베이스 연동이나 클라우드 스케일아웃이 필요한 경우, `docker-compose.yml`을 통해 Ubuntu 기반의 Headless 워커 노드로 즉각 전환할 수 있습니다.
- **Volume Mounting**: 볼륨 마운트(`C:\ameva:/app/data`)를 통해 컨테이너 내부의 처리 결과는 즉시 Windows 호스트의 GUI 뷰어에서 확인 가능합니다.

---

## 5. 설치 및 실행 (Getting Started)

### 5.1 로컬 실행 (Windows)
1. **의존성 설치**:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. **모델 다운로드**: `python src/utils/download_models.py` (Whisper 및 Vosk 모델 자동 설치)
3. **앱 구동**: `python main.py`

### 5.2 도커 실행 (Optional)
```cmd
docker-compose -f docker/docker-compose.yml up --build -d
```

---

## 6. 기술적 Deep Dive

### 6.1 `src/core/pipeline.py`
Python의 GIL을 우회하기 위해 `multiprocessing`을 활용하며, Windows 환경의 안정성을 위해 `spawn` 방식과 `Manager.Queue` 하트비트 로직을 구현하였습니다.

### 6.2 주요 라이브러리 명세
*   **pywhispercpp**: whisper.cpp의 C++ 바인딩으로 저사양 CPU 가속 지원.
*   **vosk**: Kaldi 기반 오프라인 화자 식별 엔진.
*   **PyQt6**: 네이티브 성능의 고해상도 GUI 프레임워크.
*   **scikit-learn**: K-Means 군집화 및 PCA 연산 담당.

---

본 프로젝트는 단순한 기능을 넘어, 음성 처리 파이프라인에서 발생할 수 있는 엣지 케이스를 공학적으로 해결하고 대규모 데이터 처리의 안정성을 확보하는 데 중점을 두었습니다.
