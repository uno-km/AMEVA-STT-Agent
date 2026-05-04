from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QComboBox, 
    QSpinBox, QDoubleSpinBox, QPushButton, QLabel, QMessageBox
)
from src.core.settings_manager import settings_manager

class SettingsPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("⚙️ 파라미터 세팅 (Panel 2)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        form_layout = QFormLayout()

        # Theme
        self.cb_theme = QComboBox()
        self.cb_theme.addItems(["dark", "light"])
        form_layout.addRow("테마 모드:", self.cb_theme)

        # Whisper Model
        self.cb_model = QComboBox()
        self.cb_model.addItems(["ggml-medium-q5_0.bin", "ggml-large-v3-turbo-q5_0.bin"])
        form_layout.addRow("Whisper 모델:", self.cb_model)

        # Language
        self.cb_lang = QComboBox()
        self.cb_lang.addItems(["ko", "en", "auto"])
        form_layout.addRow("타겟 언어:", self.cb_lang)

        # Threads
        self.sb_threads = QSpinBox()
        self.sb_threads.setRange(1, 32)
        form_layout.addRow("CPU 스레드 수:", self.sb_threads)

        # Temperature
        self.db_temp = QDoubleSpinBox()
        self.db_temp.setRange(0.0, 1.0)
        self.db_temp.setSingleStep(0.1)
        form_layout.addRow("Temperature:", self.db_temp)

        # Diarization Margin
        self.db_margin = QDoubleSpinBox()
        self.db_margin.setRange(0.0, 5.0)
        self.db_margin.setSingleStep(0.1)
        form_layout.addRow("화자분리 오차범위:", self.db_margin)

        layout.addLayout(form_layout)

        # Save Button
        self.btn_save = QPushButton("💾 설정 저장하기")
        self.btn_save.setStyleSheet("background-color: #89b4fa; color: #11111b; font-weight: bold; padding: 5px;")
        self.btn_save.clicked.connect(self.save_settings)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()

    def load_current_settings(self):
        settings = settings_manager.settings
        
        # Theme
        theme = settings.get("theme", "dark")
        self.cb_theme.setCurrentText(theme)

        # STT
        stt = settings.get("stt", {})
        self.cb_model.setCurrentText(stt.get("model", "ggml-medium-q5_0.bin"))
        self.cb_lang.setCurrentText(stt.get("language", "ko"))
        self.sb_threads.setValue(stt.get("threads", 4))
        self.db_temp.setValue(stt.get("temperature", 0.0))

        # Diarization
        dia = settings.get("diarization", {})
        self.db_margin.setValue(dia.get("margin", 0.5))

    def save_settings(self):
        settings_manager.settings["theme"] = self.cb_theme.currentText()
        
        if "stt" not in settings_manager.settings:
            settings_manager.settings["stt"] = {}
        settings_manager.settings["stt"]["model"] = self.cb_model.currentText()
        settings_manager.settings["stt"]["language"] = self.cb_lang.currentText()
        settings_manager.settings["stt"]["threads"] = self.sb_threads.value()
        settings_manager.settings["stt"]["temperature"] = self.db_temp.value()

        if "diarization" not in settings_manager.settings:
            settings_manager.settings["diarization"] = {}
        settings_manager.settings["diarization"]["margin"] = self.db_margin.value()

        settings_manager.save_settings()
        QMessageBox.information(self, "저장 완료", "설정이 settings.json에 저장되었습니다.")
