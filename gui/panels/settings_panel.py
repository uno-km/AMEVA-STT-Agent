import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, 
    QPushButton, QLabel, QCheckBox, QSpinBox, QMessageBox, QFrame
)
from src.core.settings_manager import settings_manager

class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_from_json()

    def init_ui(self):
        layout = QVBoxLayout(self)
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
        
        # 모델 설정 섹션
        model_label = QLabel("STT 모델 설정")
        model_label.setStyleSheet("font-weight: bold; color: #c3e88d; margin-top: 10px;")
        form.addRow(model_label)

        self.combo_model = QComboBox()
        self.combo_model.addItems(["small", "medium", "turbo", "large-v3"])
        form.addRow("Whisper 모델:", self.combo_model)

        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["ko", "en", "ja", "zh", "auto"])
        form.addRow("대상 언어:", self.combo_lang)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 64)
        form.addRow("작업 스레드:", self.spin_threads)

        # 시스템 섹션
        sys_label = QLabel("시스템 환경")
        sys_label.setStyleSheet("font-weight: bold; color: #ffcb6b; margin-top: 10px;")
        form.addRow(sys_label)

        self.check_dark = QCheckBox("다크보드 테마 적용")
        self.check_dark.setChecked(True)
        form.addRow("테마:", self.check_dark)

        layout.addLayout(form)

        layout.addStretch()

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
        layout.addWidget(self.btn_save)

    def load_from_json(self):
        # 모델 상태 체크 및 콤보박스 업데이트
        self.update_model_list()
        
        s = settings_manager.get("stt")
        current_model = s.get("model", "medium")
        # 상태 표시가 포함된 텍스트에서 매칭되는 항목 찾기
        for i in range(self.combo_model.count()):
            if current_model in self.combo_model.itemText(i):
                self.combo_model.setCurrentIndex(i)
                break
        
        self.combo_lang.setCurrentText(s.get("language", "ko"))
        self.spin_threads.setValue(s.get("threads", 4))
        
        theme = settings_manager.get("theme")
        self.check_dark.setChecked(theme == "dark")

    def update_model_list(self):
        self.combo_model.clear()
        base_dir = r"C:\ameva\AI_Models\faster-whisper"
        models = ["small", "medium", "turbo", "large-v3"]
        
        for m in models:
            # HuggingFace 캐시 폴더 패턴 확인
            folder_name = f"models--Systran--faster-whisper-{m}"
            if m == "turbo": folder_name = "models--Systran--faster-whisper-large-v3-turbo"
            
            exists = False
            if os.path.exists(os.path.join(base_dir, folder_name)):
                exists = True
            
            display_text = f"{m} {'✅' if exists else '❌'}"
            self.combo_model.addItem(display_text, m)

    def save_to_json(self):
        # 실제 모델명만 추출 (✅ ❌ 제외)
        selected_text = self.combo_model.currentText().split()[0]
        settings_manager.settings["stt"]["model"] = selected_text
        settings_manager.settings["stt"]["language"] = self.combo_lang.currentText()
        settings_manager.settings["stt"]["threads"] = self.spin_threads.value()
        settings_manager.settings["theme"] = "dark" if self.check_dark.isChecked() else "light"
        
        settings_manager.save()
        QMessageBox.information(self, "저장 완료", "설정이 성공적으로 저장되었습니다.")
        self.update_model_list() # 상태 새로고침
