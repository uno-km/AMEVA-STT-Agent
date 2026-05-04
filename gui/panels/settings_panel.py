import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, 
    QPushButton, QLabel, QCheckBox, QSpinBox, QMessageBox
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

        title = QLabel("⚙️ STT 엔진 파라미터 설정")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #82aaff; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        
        # 모델 선택 (Small, Medium, Turbo)
        self.combo_model = QComboBox()
        self.combo_model.addItems(["small", "medium", "turbo (v3)"])
        form.addRow("Whisper 모델 사이즈:", self.combo_model)

        # 언어 설정
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["ko", "en", "ja", "zh"])
        form.addRow("대상 언어 (Language):", self.combo_lang)

        # CPU 스레드
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, 32)
        self.spin_threads.setValue(4)
        form.addRow("CPU 작업 스레드 수:", self.spin_threads)

        # 다크모드 여부
        self.check_dark = QCheckBox("다크보드 테마 적용")
        self.check_dark.setChecked(True)
        form.addRow("UI 테마:", self.check_dark)

        layout.addLayout(form)

        # 저장 버튼
        self.btn_save = QPushButton("💾 설정 저장하기 (settings.json)")
        self.btn_save.setStyleSheet("""
            QPushButton { background-color: #3b4252; padding: 10px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #4c566a; }
        """)
        self.btn_save.clicked.connect(self.save_to_json)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()

    def load_from_json(self):
        s = settings_manager.get("stt")
        self.combo_model.setCurrentText(s.get("model", "medium"))
        self.combo_lang.setCurrentText(s.get("language", "ko"))
        self.spin_threads.setValue(s.get("threads", 4))
        
        # UI settings
        u = settings_manager.get("theme")
        self.check_dark.setChecked(u == "dark")

    def save_to_json(self):
        settings_manager.settings["stt"]["model"] = self.combo_model.currentText()
        settings_manager.settings["stt"]["language"] = self.combo_lang.currentText()
        settings_manager.settings["stt"]["threads"] = self.spin_threads.value()
        settings_manager.settings["theme"] = "dark" if self.check_dark.isChecked() else "light"
        
        settings_manager.save()
        QMessageBox.information(self, "저장 완료", "설정이 settings.json에 저장되었습니다.")
