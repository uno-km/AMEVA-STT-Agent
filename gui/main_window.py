import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QApplication
)
from PyQt6.QtCore import Qt

# Import panels (to be implemented)
from gui.panels.logging_chart import LoggingChartPanel
from gui.panels.settings_panel import SettingsPanel
from gui.panels.result_viewer import ResultViewerPanel
from gui.panels.batch_control import BatchControlPanel
from src.core.settings_manager import settings_manager
from src.utils.worker import PipelineWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA Hybrid STT Engine Dashboard")
        self.resize(1280, 800)
        self.apply_theme()

        self.init_ui()
        settings_manager.settings_changed.connect(self.on_settings_changed)

    def init_ui(self):
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Main Splitter (Horizontal: Left Side / Right Side)
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left Splitter (Vertical: Top-Left / Bottom-Left)
        v_splitter_left = QSplitter(Qt.Orientation.Vertical)
        
        # Right Splitter (Vertical: Top-Right / Bottom-Right)
        v_splitter_right = QSplitter(Qt.Orientation.Vertical)

        # Initialize Panels
        self.panel_logging = LoggingChartPanel()
        self.panel_settings = SettingsPanel()
        self.panel_viewer = ResultViewerPanel()
        self.panel_batch = BatchControlPanel()

        # Add to left splitter
        v_splitter_left.addWidget(self.panel_logging)
        v_splitter_left.addWidget(self.panel_settings)
        # Default ratios for left (e.g. 60% logging, 40% settings)
        v_splitter_left.setSizes([600, 400])

        # Add to right splitter
        v_splitter_right.addWidget(self.panel_viewer)
        v_splitter_right.addWidget(self.panel_batch)
        # Default ratios for right (e.g. 70% viewer, 30% batch)
        v_splitter_right.setSizes([700, 300])

        # Add to main splitter
        h_splitter.addWidget(v_splitter_left)
        h_splitter.addWidget(v_splitter_right)
        h_splitter.setSizes([600, 680])

        main_layout.addWidget(h_splitter)

        # Wire up signals
        self.panel_batch.btn_run.clicked.connect(self.start_batch_pipeline)
        
    def start_batch_pipeline(self):
        input_dir = self.panel_batch.le_input.text()
        output_dir = self.panel_batch.le_output.text()
        
        self.worker = PipelineWorker(input_dir, output_dir)
        self.worker.log_signal.connect(self.panel_logging.append_log)
        self.worker.chart_signal.connect(self.panel_logging.update_chart)
        self.worker.finished_signal.connect(self.panel_viewer.open_file_in_tab)
        self.worker.start()

    def apply_theme(self):
        theme = settings_manager.get("theme")
        if theme == "dark":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1e1e2e;
                    color: #cdd6f4;
                }
                QSplitter::handle {
                    background-color: #313244;
                }
                QSplitter::handle:horizontal {
                    width: 4px;
                }
                QSplitter::handle:vertical {
                    height: 4px;
                }
                QSplitter::handle:pressed {
                    background-color: #89b4fa;
                }
            """)
        else:
            self.setStyleSheet("") # Default OS theme

    def on_settings_changed(self, new_settings):
        # When settings change, we can re-apply theme or update UI
        self.apply_theme()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
