import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QApplication
)
from PyQt6.QtCore import Qt

from gui.panels.logging_chart import LoggingChartPanel
from gui.panels.settings_panel import SettingsPanel
from gui.panels.explorer_panel import ExplorerPanel
from gui.panels.viewer_panel import ViewerPanel
from gui.panels.batch_control import BatchControlPanel
from src.core.settings_manager import settings_manager
from src.utils.worker import PipelineWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMEVA Hybrid STT Dashboard v2.5 - Expert Edition")
        self.resize(1700, 950)
        self.worker = None
        
        self.init_ui()
        # 초기 테마 적용
        theme = settings_manager.get("theme")
        self.apply_theme(theme if isinstance(theme, str) else "dark")
        
        # 설정 변경 감지 시 테마 업데이트
        settings_manager.settings_changed.connect(lambda s: self.apply_theme(s.get("theme", "dark")))

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 메인 가로 분할기 (3단 구성)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. 왼쪽 사이드바: 익스플로러
        self.p_explorer = ExplorerPanel()
        self.main_splitter.addWidget(self.p_explorer)

        # 2. 중앙 영역: 메인 뷰어 (상) / 로그 (하)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        self.center_v_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.p_viewer = ViewerPanel()
        self.p_log = LoggingChartPanel()
        
        self.center_v_splitter.addWidget(self.p_viewer)
        self.center_v_splitter.addWidget(self.p_log)
        self.center_v_splitter.setSizes([600, 300])
        
        center_layout.addWidget(self.center_v_splitter)
        self.main_splitter.addWidget(center_widget)

        # 3. 오른쪽 사이드바: 설정 및 배치 관리
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.right_v_splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.p_settings = SettingsPanel()
        self.p_batch = BatchControlPanel()
        
        self.right_v_splitter.addWidget(self.p_settings)
        self.right_v_splitter.addWidget(self.p_batch)
        self.right_v_splitter.setSizes([400, 500])
        
        right_layout.addWidget(self.right_v_splitter)
        self.main_splitter.addWidget(right_widget)

        # 초기 너비 비율 설정
        self.main_splitter.setSizes([250, 1000, 450])

        main_layout.addWidget(self.main_splitter)

        # --- Signal Connections ---
        
        # 익스플로러에서 파일 선택 시 뷰어에 표시
        self.p_explorer.file_selected.connect(self.p_viewer.open_file_in_tab)
        
        # 배치 실행 버튼 및 자동 타이머 신호 연결
        self.p_batch.btn_run_batch.clicked.connect(self.start_pipeline)
        self.p_batch.run_requested.connect(self.start_pipeline)

    def start_pipeline(self):
        if self.worker and self.worker.isRunning():
            self.p_log.append_log("⚠️ 이미 분석 작업이 진행 중입니다. 현재 작업 완료 후 다음 주기에 시작합니다.")
            return

        input_dir = self.p_batch.line_input.text()
        output_dir = self.p_batch.line_output.text()
        
        self.worker = PipelineWorker(input_dir, output_dir)
        # 로깅 및 차트 업데이트
        self.worker.log_signal.connect(self.p_log.append_log)
        self.worker.chart_signal.connect(self.p_log.update_chart)
        # 작업 완료 시 뷰어 자동 업데이트 및 배치 리스트 새로고침
        self.worker.finished_signal.connect(self.p_viewer.open_file_in_tab)
        self.worker.finished_signal.connect(lambda: self.p_batch.refresh_log())
        
        self.worker.start()

    def apply_theme(self, theme_name):
        if theme_name == "light":
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #ffffff; color: #24292f; font-family: 'Segoe UI', 'Malgun Gothic'; }
                QSplitter::handle { background-color: #d0d7de; }
                
                /* Buttons */
                QPushButton { 
                    background-color: #f6f8fa; 
                    border: 1px solid #d0d7de; 
                    border-radius: 6px; 
                    padding: 6px 12px; 
                    color: #24292f; 
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #f3f4f6; border-color: #0969da; }
                QPushButton#btn_run_batch { background-color: #2da44e; color: white; border: none; }
                QPushButton#btn_run_batch:hover { background-color: #2c974b; }

                /* Inputs */
                QLineEdit, QSpinBox, QComboBox { 
                    background-color: #ffffff; 
                    border: 1px solid #d0d7de; 
                    padding: 5px; 
                    border-radius: 6px; 
                    color: #24292f; 
                }
                QLineEdit:focus { border: 2px solid #0969da; }

                /* Panels specific styles */
                QTextEdit, QTextBrowser { 
                    background-color: #f6f8fa; 
                    border: 1px solid #d0d7de; 
                    border-radius: 6px; 
                    color: #24292f; 
                    font-family: 'Consolas', monospace;
                }
                QTreeView { 
                    background-color: #ffffff; 
                    border: none; 
                    color: #24292f;
                }
                QTreeView::item:selected { background-color: #ddf4ff; color: #0969da; }
                
                QHeaderView::section { background-color: #f6f8fa; color: #57606a; padding: 4px; border: none; font-weight: bold; }
                
                QTableWidget { 
                    background-color: #ffffff; 
                    gridline-color: #d0d7de; 
                    border: 1px solid #d0d7de;
                }
                
                /* Tabs */
                QTabWidget::pane { border: 1px solid #d0d7de; top: -1px; background-color: #ffffff; }
                QTabBar::tab { 
                    background: #f6f8fa; 
                    border: 1px solid #d0d7de; 
                    border-bottom-color: transparent; 
                    border-top-left-radius: 6px; 
                    border-top-right-radius: 6px; 
                    padding: 8px 16px; 
                    margin-right: 2px;
                    color: #57606a;
                }
                QTabBar::tab:selected { background: #ffffff; color: #24292f; font-weight: bold; border-bottom-color: #ffffff; }
                
                QLabel#title { color: #0969da; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #0f111a; color: #d1d4e0; font-family: 'Segoe UI', 'Malgun Gothic'; }
                QSplitter::handle { background-color: #2e3c43; }
                
                QPushButton { 
                    background-color: #3b4252; 
                    border: 1px solid #4c566a; 
                    border-radius: 4px; 
                    padding: 5px; 
                    color: white; 
                }
                QPushButton:hover { background-color: #4c566a; border: 1px solid #82aaff; }
                
                QLineEdit, QSpinBox, QComboBox { 
                    background-color: #1a1b26; 
                    border: 1px solid #2e3c43; 
                    padding: 4px; 
                    border-radius: 3px; 
                    color: #d1d4e0; 
                }
                
                QTextEdit, QTextBrowser { 
                    background-color: #1a1b26; 
                    color: #d1d4e0; 
                    border: 1px solid #2e3c43;
                }
                
                QTabWidget::pane { border: 1px solid #2e3c43; }
                QTabBar::tab { background: #2e3c43; padding: 8px; margin: 2px; border-radius: 4px; }
                QTabBar::tab:selected { background: #3b4252; border: 1px solid #82aaff; }
                
                QTreeView { background-color: #1a1b26; border: none; color: #d1d4e0; }
                QHeaderView::section { background-color: #2e3c43; color: white; }
                QTableWidget { background-color: #1a1b26; gridline-color: #2e3c43; }
            """)

