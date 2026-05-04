import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QApplication, QFrame
)
from PyQt6.QtCore import Qt

from gui.panels.logging_chart import LoggingChartPanel
from gui.panels.settings_panel import SettingsPanel
from gui.panels.result_viewer import ResultViewerPanel
from gui.panels.batch_control import BatchControlPanel
from src.core.settings_manager import settings_manager
from src.utils.worker import PipelineWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA Hybrid STT Dashboard v2.0")
        self.resize(1400, 900)
        
        self.init_ui()
        self.apply_styles()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)

        # 메인 가로 분할기 (좌/우)
        main_h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 좌측 영역 (상단: 로깅/차트, 하단: 설정)
        left_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.p1 = LoggingChartPanel()
        self.p2 = SettingsPanel()
        left_v_splitter.addWidget(self.p1)
        left_v_splitter.addWidget(self.p2)
        left_v_splitter.setSizes([500, 400])

        # 우측 영역 (상단: 결과 뷰어, 하단: 배치 컨트롤)
        right_v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.p3 = ResultViewerPanel()
        self.p4 = BatchControlPanel()
        right_v_splitter.addWidget(self.p3)
        right_v_splitter.addWidget(self.p4)
        right_v_splitter.setSizes([600, 300])

        main_h_splitter.addWidget(left_v_splitter)
        main_h_splitter.addWidget(right_v_splitter)
        main_h_splitter.setSizes([600, 800])

        layout.addWidget(main_h_splitter)

        # Worker 연결
        self.worker = None
        self.p4.btn_run_batch.clicked.connect(self.start_pipeline)

    def start_pipeline(self):
        input_dir = self.p4.line_input.text()
        output_dir = self.p4.line_output.text()
        
        self.worker = PipelineWorker(input_dir, output_dir)
        # 로깅 패널 연결
        self.worker.log_signal.connect(self.p1.append_log)
        self.worker.chart_signal.connect(self.p1.update_chart)
        # 뷰어 패널 연결
        self.worker.finished_signal.connect(self.p3.open_file_in_tab)
        
        self.worker.start()

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #0f111a; }
            QSplitter::handle { background-color: #2e3c43; }
            QSplitter::handle:horizontal { width: 2px; }
            QSplitter::handle:vertical { height: 2px; }
            QWidget { color: #d1d4e0; font-family: 'Segoe UI', 'Malgun Gothic'; }
        """)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
