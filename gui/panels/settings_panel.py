import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, 
    QPushButton, QLabel, QCheckBox, QSpinBox, QMessageBox, QFrame,
    QHBoxLayout, QProgressBar, QDoubleSpinBox, QScrollArea
)
from PyQt6.QtCore import pyqtSignal
from src.core.settings_manager import settings_manager
from src.utils.downloader import ModelDownloader

class SettingsPanel(QWidget):
    download_log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.downloader = None
        self.init_ui()
        self.load_from_json()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 스크롤 영역 추가 (설정이 많아질 것에 대비)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("⚙️ 시스템 설정")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #82aaff; margin-bottom: 10px;")
        layout.addWidget(title)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #2e3c43;")
        layout.addWidget(line)

        form = QFormLayout()
        form.setSpacing(10)
        
        # --- STT 모델 설정 섹션 ---
        model_label = QLabel("STT 모델 및 기본 설정")
        model_label.setStyleSheet("font-weight: bold; color: #c3e88d; margin-top: 10px;")
        form.addRow(model_label)

        self.combo_model = QComboBox()
        self.btn_download = QPushButton("📥 다운로드")
        self.btn_download.setFixedWidth(100)
        self.btn_download.clicked.connect(self.start_download)
        
        model_layout = QHBoxLayout()
        model_layout.addWidget(self.combo_model)
        model_layout.addWidget(self.btn_download)
        form.addRow("Whisper 모델:", model_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #88c0d0; }")
        form.addRow("", self.progress_bar)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["ko", "en", "ja", "zh", "auto"])
        form.addRow("대상 언어:", self.combo_lang)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 64)
        form.addRow("작업 스레드:", self.spin_threads)

        # --- Diarization 섹션 ---
        dia_label = QLabel("Diarization (화자 분리 설정)")
        dia_label.setStyleSheet("font-weight: bold; color: #ffcb6b; margin-top: 15px;")
        form.addRow(dia_label)

        self.spin_speakers = QSpinBox()
        self.spin_speakers.setRange(0, 10)
        self.spin_speakers.setSpecialValueText("Auto")
        form.addRow("예상 화자 수:", self.spin_speakers)

        self.spin_offset = QDoubleSpinBox()
        self.spin_offset.setRange(0.1, 10.0)
        self.spin_offset.setSingleStep(0.1)
        self.spin_offset.setSuffix(" 초")
        form.addRow("매핑 허용 오차:", self.spin_offset)

        # --- Whisper.cpp 고급 설정 ---
        engine_label = QLabel("Whisper.cpp (고급 엔진 파라미터)")
        engine_label.setStyleSheet("font-weight: bold; color: #f07178; margin-top: 15px;")
        form.addRow(engine_label)

        self.spin_max_len = QSpinBox()
        self.spin_max_len.setRange(0, 500)
        self.spin_max_len.setSpecialValueText("Unlimited")
        form.addRow("문장 최대 길이:", self.spin_max_len)

        self.check_sow = QCheckBox("단어 경계 기준 분할 (-sow)")
        form.addRow("단어 단위 분리:", self.check_sow)

        # --- VAD 설정 ---
        vad_label = QLabel("VAD (음성 활동 감지)")
        vad_label.setStyleSheet("font-weight: bold; color: #89ddff; margin-top: 15px;")
        form.addRow(vad_label)

        self.check_vad = QCheckBox("VAD 엔진 활성화")
        form.addRow("VAD 사용:", self.check_vad)

        self.spin_vad_max = QSpinBox()
        self.spin_vad_max.setRange(1, 60)
        self.spin_vad_max.setSuffix(" 초")
        form.addRow("최대 음성 시간:", self.spin_vad_max)

        self.spin_vad_min = QSpinBox()
        self.spin_vad_min.setRange(10, 5000)
        self.spin_vad_min.setSingleStep(100)
        self.spin_vad_min.setSuffix(" ms")
        form.addRow("최소 침묵 시간:", self.spin_vad_min)

        # --- 시스템 섹션 ---
        sys_label = QLabel("시스템 환경")
        sys_label.setStyleSheet("font-weight: bold; color: #82aaff; margin-top: 15px;")
        form.addRow(sys_label)

        self.check_dark = QCheckBox("다크보드 테마 적용")
        form.addRow("테마:", self.check_dark)

        layout.addLayout(form)
        layout.addStretch()
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # 저장 버튼
        self.btn_save = QPushButton("💾 설정값 저장 (settings.json)")
        self.btn_save.setStyleSheet("""
            QPushButton { 
                background-color: #3b4252; 
                padding: 12px; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 13px;
                border: 1px solid #4c566a;
            }
            QPushButton:hover { background-color: #4c566a; border: 1px solid #82aaff; }
        """)
        self.btn_save.clicked.connect(self.save_to_json)
        main_layout.addWidget(self.btn_save)

    def load_from_json(self):
        # 모델 상태 체크 및 콤보박스 업데이트
        self.update_model_list()
        
        s = settings_manager.get("stt")
        current_model = s.get("model", "medium")
        # 데이터(UserData) 기반으로 매칭되는 항목 찾기
        index = self.combo_model.findData(current_model)
        if index >= 0:
            self.combo_model.setCurrentIndex(index)
        else:
            # 못 찾으면 텍스트 부분 일치 확인 (하위 호환)
            for i in range(self.combo_model.count()):
                if current_model in self.combo_model.itemText(i):
                    self.combo_model.setCurrentIndex(i)
                    break
        
        self.combo_lang.setCurrentText(s.get("language", "ko"))
        self.spin_threads.setValue(s.get("threads", 4))
        
        # Expert fields
        self.spin_speakers.setValue(s.get("speakers", 2))
        self.spin_offset.setValue(s.get("max_offset", 2.0))
        self.spin_max_len.setValue(s.get("max_len", 20))
        self.check_sow.setChecked(s.get("split_on_word", True))
        self.check_vad.setChecked(s.get("vad_enabled", False))
        self.spin_vad_max.setValue(s.get("vad_max_speech_duration", 5))
        self.spin_vad_min.setValue(s.get("vad_min_silence_duration", 500))

        theme = settings_manager.get("theme")
        self.check_dark.setChecked(theme == "dark")

    def update_model_list(self):
        self.combo_model.clear()
        base_dir = r"C:\ameva\AI_Models\ggml"
        models = ["small", "medium", "turbo", "large"]
        
        for m in models:
            # GGML 파일명 패턴 확인 (양자화 버전 포함 검색)
            base_filename = f"ggml-{m}"
            if m == "turbo": base_filename = "ggml-large-v3-turbo"
            elif m == "large": base_filename = "ggml-large-v3"
            
            exists = False
            # 폴더 내의 파일들을 뒤져서 해당 모델명이 포함된 .bin 파일이 있는지 확인
            if os.path.exists(base_dir):
                for f in os.listdir(base_dir):
                    if f.startswith(base_filename) and f.endswith(".bin") and os.path.getsize(os.path.join(base_dir, f)) > 1024*1024:
                        exists = True
                        break
            
            display_text = f"{m} {'✅' if exists else '❌'}"
            self.combo_model.addItem(display_text, m)

    def save_to_json(self):
        # UserData에서 실제 모델명(small, medium 등) 직접 추출
        selected_model = self.combo_model.currentData()
        if not selected_model:
            selected_model = self.combo_model.currentText().split()[0]
            
        settings_manager.settings["stt"]["model"] = selected_model
        settings_manager.settings["stt"]["language"] = self.combo_lang.currentText()
        settings_manager.settings["stt"]["threads"] = self.spin_threads.value()
        
        # Expert fields save
        settings_manager.settings["stt"]["speakers"] = self.spin_speakers.value()
        settings_manager.settings["stt"]["max_offset"] = self.spin_offset.value()
        settings_manager.settings["stt"]["max_len"] = self.spin_max_len.value()
        settings_manager.settings["stt"]["split_on_word"] = self.check_sow.isChecked()
        settings_manager.settings["stt"]["vad_enabled"] = self.check_vad.isChecked()
        settings_manager.settings["stt"]["vad_max_speech_duration"] = self.spin_vad_max.value()
        settings_manager.settings["stt"]["vad_min_silence_duration"] = self.spin_vad_min.value()

        settings_manager.settings["theme"] = "dark" if self.check_dark.isChecked() else "light"
        
        settings_manager.save()
        QMessageBox.information(self, "저장 완료", "설정이 성공적으로 저장되었습니다.")
        self.update_model_list() # 상태 새로고침

    def start_download(self):
        # 실제 모델명만 추출
        model_name = self.combo_model.currentData()
        if not model_name:
            model_name = self.combo_model.currentText().split()[0]
            
        base_dir = r"C:\ameva\AI_Models\ggml"
        
        self.downloader = ModelDownloader(model_name, base_dir)
        self.downloader.progress_signal.connect(self.progress_bar.setValue)
        self.downloader.log_signal.connect(self.download_log_signal.emit)
        self.downloader.finished_signal.connect(self.on_download_finished)
        
        self.btn_download.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.downloader.start()

    def on_download_finished(self, success):
        self.btn_download.setEnabled(True)
        self.progress_bar.setVisible(False)
        if success:
            self.update_model_list()
            # 콤보박스 선택 유지
            for i in range(self.combo_model.count()):
                if self.downloader.model_name in self.combo_model.itemText(i):
                    self.combo_model.setCurrentIndex(i)
                    break
            QMessageBox.information(self, "다운로드 완료", f"{self.downloader.model_name} 모델이 설치되었습니다.")
        else:
            QMessageBox.warning(self, "다운로드 실패", "모델 다운로드 중 오류가 발생했습니다.")
