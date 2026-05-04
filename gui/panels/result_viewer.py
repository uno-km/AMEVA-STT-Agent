from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QTreeView, QFileSystemModel, QTabWidget, QLabel, QTextEdit
)
from PyQt6.QtCore import Qt, QDir
import os

class ResultViewerPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("📂 STT 결과 뷰어 (Panel 3)")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # File Explorer (QTreeView)
        self.tree_view = QTreeView()
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.rootPath())
        self.file_model.setNameFilters(["*.json", "*.csv", "*.txt", "*.wav"])
        self.file_model.setNameFilterDisables(False)
        self.tree_view.setModel(self.file_model)
        
        # Set root to workspace or C: drive
        workspace_path = r"C:\ameva\AMEVA-STT-Agent"
        if os.path.exists(workspace_path):
            self.tree_view.setRootIndex(self.file_model.index(workspace_path))
        
        self.tree_view.doubleClicked.connect(self.on_file_double_clicked)
        splitter.addWidget(self.tree_view)

        # Tab Viewer
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setUsesScrollButtons(True) # Overflow handling
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        
        # Default instruction tab
        default_tab = QTextEdit()
        default_tab.setReadOnly(True)
        default_tab.setText("좌측 탐색기에서 파일을 더블클릭하여 내용을 확인하세요.")
        default_tab.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.tab_widget.addTab(default_tab, "안내")
        
        splitter.addWidget(self.tab_widget)
        splitter.setSizes([200, 500])

        layout.addWidget(splitter)

    def on_file_double_clicked(self, index):
        file_path = self.file_model.filePath(index)
        if not os.path.isdir(file_path):
            self.open_file_in_tab(file_path)

    def open_file_in_tab(self, file_path):
        filename = os.path.basename(file_path)
        
        # Check if already open
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == filename:
                self.tab_widget.setCurrentIndex(i)
                return

        # Create new tab
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4; font-family: Consolas;")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                text_edit.setText(content)
        except Exception as e:
            text_edit.setText(f"파일을 읽을 수 없습니다:\n{e}")

        idx = self.tab_widget.addTab(text_edit, filename)
        self.tab_widget.setCurrentIndex(idx)

    def close_tab(self, index):
        self.tab_widget.removeTab(index)
