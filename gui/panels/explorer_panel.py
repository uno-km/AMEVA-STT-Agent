import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QLabel
from PyQt6.QtGui import QFileSystemModel
from PyQt6.QtCore import Qt, QDir, pyqtSignal

class ExplorerPanel(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("📂 EXPLORER")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #88c0d0; margin: 5px;")
        layout.addWidget(title)

        self.tree_view = QTreeView()
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.rootPath())
        self.file_model.setNameFilters(["*.json", "*.csv", "*.txt", "*.wav", "*.mp3"])
        self.file_model.setNameFilterDisables(False)
        self.tree_view.setModel(self.file_model)
        
        # Set root to workspace
        workspace_path = r"C:\ameva\AMEVA-STT-Agent"
        if os.path.exists(workspace_path):
            self.tree_view.setRootIndex(self.file_model.index(workspace_path))
        
        self.tree_view.doubleClicked.connect(self.on_double_clicked)
        self.tree_view.setStyleSheet("""
            QTreeView { background-color: #1a1b26; border: none; }
            QHeaderView::section { background-color: #2e3c43; color: white; }
        """)
        
        # Hide columns except name
        for i in range(1, 4):
            self.tree_view.hideColumn(i)

        layout.addWidget(self.tree_view)

    def on_double_clicked(self, index):
        file_path = self.file_model.filePath(index)
        if not os.path.isdir(file_path):
            self.file_selected.emit(file_path)
