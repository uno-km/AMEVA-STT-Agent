import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QHBoxLayout, QLabel, QSpinBox, QFileDialog
)
from src.core.settings_manager import settings_manager

class BatchControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_paths()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("⏱️ 배치 주기 및 경로 설정")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffcb6b; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()

        # 입력 폴더
        self.line_input = QLineEdit()
        btn_browse_in = QPushButton("찾기")
        btn_browse_in.clicked.connect(lambda: self.browse("input"))
        h1 = QHBoxLayout()
        h1.addWidget(self.line_input)
        h1.addWidget(btn_browse_in)
        form.addRow("분석 대상 폴더:", h1)

        # 출력 폴더
        self.line_output = QLineEdit()
        btn_browse_out = QPushButton("찾기")
        btn_browse_out.clicked.connect(lambda: self.browse("output"))
        h2 = QHBoxLayout()
        h2.addWidget(self.line_output)
        h2.addWidget(btn_browse_out)
        form.addRow("STT 결과 저장 폴더:", h2)

        # 배치 주기
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 1440)
        self.spin_interval.setSuffix(" 분")
        form.addRow("자동 배치 실행 주기:", self.spin_interval)

        layout.addLayout(form)

        # 경로 저장 버튼
        btn_layout = QHBoxLayout()
        self.btn_save_path = QPushButton("📁 경로 및 주기 저장")
        self.btn_save_path.setStyleSheet("background-color: #4f5b66; padding: 10px; font-weight: bold;")
        self.btn_save_path.clicked.connect(self.save_paths)
        
        self.btn_run_batch = QPushButton("🚀 배치 즉시 실행")
        self.btn_run_batch.setStyleSheet("background-color: #bf616a; padding: 10px; font-weight: bold;")
        
        btn_layout.addWidget(self.btn_save_path)
        btn_layout.addWidget(self.btn_run_batch)
        layout.addLayout(btn_layout)

    def browse(self, target):
        path = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if path:
            if target == "input": self.line_input.setText(path)
            else: self.line_output.setText(path)

    def load_paths(self):
        b = settings_manager.get("batch")
        self.line_input.setText(b.get("input_dir", ""))
        self.line_output.setText(b.get("output_dir", ""))
        self.spin_interval.setValue(b.get("interval_min", 60))

    def save_paths(self):
        settings_manager.settings["batch"]["input_dir"] = self.line_input.text()
        settings_manager.settings["batch"]["output_dir"] = self.line_output.text()
        settings_manager.settings["batch"]["interval_min"] = self.spin_interval.value()
        settings_manager.save()
