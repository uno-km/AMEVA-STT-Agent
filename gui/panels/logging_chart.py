from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLabel, QTabWidget
from PyQt6.QtCore import pyqtSlot
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
from datetime import datetime

class LoggingChartPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #30363d; top: -1px; }
            QTabBar::tab { 
                background: #161b22; 
                color: #8b949e; 
                padding: 10px 20px; 
                border: 1px solid #30363d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background: #0d1117; color: #58a6ff; font-weight: bold; }
        """)

        # 1. System Log Tab
        self.log_system = self._create_log_browser()
        self.tabs.addTab(self.log_system, "🖥️ SYSTEM")

        # 2. Pipeline Log Tab
        self.log_pipeline = self._create_log_browser()
        self.tabs.addTab(self.log_pipeline, "⚙️ PIPELINE")

        # 3. Clustering Tab
        cluster_widget = QWidget()
        cluster_layout = QVBoxLayout(cluster_widget)
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#0d1117')
        self.figure.patch.set_facecolor('#0d1117')
        self.ax.tick_params(colors='#c9d1d9')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#30363d')
        self.ax.set_title("Speaker Clustering (PCA)", color='#c9d1d9')
        cluster_layout.addWidget(self.canvas)
        self.tabs.addTab(cluster_widget, "📊 CLUSTERING")

        layout.addWidget(self.tabs)

    def _create_log_browser(self):
        browser = QTextBrowser()
        browser.setAcceptRichText(True)
        browser.setStyleSheet("""
            background-color: #0d1117; 
            color: #c9d1d9; 
            font-family: 'Consolas', 'Monospace'; 
            border: none;
            padding: 10px;
        """)
        return browser

    @pyqtSlot(str)
    def append_system_log(self, text):
        self._append_formatted(self.log_system, text)

    @pyqtSlot(str)
    def append_log(self, text):
        # 파이프라인 로그 (기존 명칭 유지하여 호환성 확보)
        self._append_formatted(self.log_pipeline, text)
        # 로그가 들어올 때 파이프라인 탭을 보여줌 (선택사항)
        # self.tabs.setCurrentIndex(1)

    def _append_formatted(self, browser, text):
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        color = "#c9d1d9"
        tag = "INFO"
        
        if "❌" in text or "ERROR" in text.upper():
            color = "#f85149"
            tag = "FAIL"
        elif "✅" in text or "완료" in text:
            color = "#3fb950"
            tag = "DONE"
        elif "🚀" in text or "시작" in text:
            color = "#58a6ff"
            tag = "INIT"
        elif "⚠️" in text:
            color = "#d29922"
            tag = "WARN"

        rich_text = f'<span style="color: #8b949e;">[{timestamp}]</span> ' \
                    f'<span style="color: {color}; font-weight: bold;">[{tag}]</span> ' \
                    f'<span style="color: {color};">{text}</span>'
        
        browser.append(rich_text)
        browser.verticalScrollBar().setValue(browser.verticalScrollBar().maximum())

    def update_chart(self, embeddings, labels):
        # clustering tab 갱신
        self.ax.clear()
        self.ax.set_facecolor('#0d1117')
        self.ax.tick_params(colors='#c9d1d9')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#30363d')
        self.ax.set_title("Speaker Clustering (PCA)", color='#c9d1d9')
        
        if embeddings is not None and len(embeddings) > 0:
            scatter = self.ax.scatter(embeddings[:, 0], embeddings[:, 1], c=labels, cmap='viridis', alpha=0.7)
        self.canvas.draw()
