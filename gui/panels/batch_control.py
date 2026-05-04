from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QFileDialog, QSpinBox, QLabel, QHBoxLayout, QMessageBox
)
from src.core.settings_manager import settings_manager
import os

class BatchControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_current_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("⏱️ 배치 및 폴더 컨트롤 (Panel 4)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        form_layout = QFormLayout()

        # Input Folder
        self.le_input = QLineEdit()
        self.btn_input = QPushButton("찾기")
        self.btn_input.clicked.connect(self.browse_input)
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.le_input)
        input_layout.addWidget(self.btn_input)
        form_layout.addRow("분석 대상 폴더:", input_layout)

        # Output Folder
        self.le_output = QLineEdit()
        self.btn_output = QPushButton("찾기")
        self.btn_output.clicked.connect(self.browse_output)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.le_output)
        output_layout.addWidget(self.btn_output)
        form_layout.addRow("저장 대상 폴더:", output_layout)

        # Cycle Minutes
        self.sb_cycle = QSpinBox()
        self.sb_cycle.setRange(1, 1440)
        self.sb_cycle.setSuffix(" 분")
        form_layout.addRow("배치 주기:", self.sb_cycle)

        layout.addLayout(form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("💾 폴더 및 주기 저장")
        self.btn_save.setStyleSheet("background-color: #a6e3a1; color: #11111b; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_settings)
        
        self.btn_run = QPushButton("🚀 배치 즉시 실행")
        self.btn_run.setStyleSheet("background-color: #f38ba8; color: #11111b; font-weight: bold;")
        self.btn_run.clicked.connect(self.run_batch)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_run)
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "분석 대상 폴더 선택")
        if folder:
            self.le_input.setText(folder)

    def browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "저장 대상 폴더 선택")
        if folder:
            self.le_output.setText(folder)

    def load_current_settings(self):
        settings = settings_manager.settings
        batch = settings.get("batch", {})
        self.le_input.setText(batch.get("input_folder", ""))
        self.le_output.setText(batch.get("output_folder", ""))
        self.sb_cycle.setValue(batch.get("cycle_minutes", 60))

    def save_settings(self):
        if "batch" not in settings_manager.settings:
            settings_manager.settings["batch"] = {}
            
        settings_manager.settings["batch"]["input_folder"] = self.le_input.text()
        settings_manager.settings["batch"]["output_folder"] = self.le_output.text()
        settings_manager.settings["batch"]["cycle_minutes"] = self.sb_cycle.value()
        
        settings_manager.save_settings()
        QMessageBox.information(self, "저장 완료", "배치 설정이 저장되었습니다.")

    def run_batch(self):
        # To be implemented: trigger pipeline
        QMessageBox.information(self, "실행", "배치 파이프라인 시작 신호 전송 (미구현)")
