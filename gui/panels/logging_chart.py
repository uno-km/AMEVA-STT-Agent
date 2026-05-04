import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QLabel
from PyQt6.QtCore import pyqtSlot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np

class LoggingChartPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Title
        title = QLabel("📝 오디오 로깅 및 군집화 시각화 (Panel 1)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Log Text Browser
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("background-color: #11111b; color: #a6e3a1; font-family: Consolas, monospace;")
        layout.addWidget(self.log_browser, stretch=1)

        # Matplotlib Canvas for PCA/Clustering
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor('#1e1e2e')
        self.figure.patch.set_facecolor('#1e1e2e')
        self.ax.tick_params(colors='#cdd6f4')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#313244')
            
        self.ax.set_title("Vosk Speaker Embedding PCA", color='#cdd6f4')
        layout.addWidget(self.canvas, stretch=1)

    @pyqtSlot(str)
    def append_log(self, text):
        self.log_browser.append(text)

    def update_chart(self, embeddings, labels):
        # mock update
        self.ax.clear()
        self.ax.set_facecolor('#1e1e2e')
        self.ax.tick_params(colors='#cdd6f4')
        for spine in self.ax.spines.values():
            spine.set_edgecolor('#313244')
        self.ax.set_title("Vosk Speaker Embedding PCA", color='#cdd6f4')
        
        scatter = self.ax.scatter(embeddings[:, 0], embeddings[:, 1], c=labels, cmap='viridis', alpha=0.7)
        self.canvas.draw()
