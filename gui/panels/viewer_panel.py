import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTextEdit, QLabel
from PyQt6.QtCore import Qt

class ViewerPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        title = QLabel("📄 RESULT VIEWER")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #a3be8c; margin: 5px;")
        layout.addWidget(title)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #2e3c43; }
            QTabBar::tab { background: #2e3c43; padding: 8px; margin: 2px; border-radius: 4px; }
            QTabBar::tab:selected { background: #3b4252; border: 1px solid #82aaff; }
        """)
        
        # Default tab
        welcome = QTextEdit()
        welcome.setReadOnly(True)
        welcome.setText("탐색기에서 파일을 선택하여 분석 결과를 확인하세요.")
        welcome.setStyleSheet("background-color: #1e1e2e; color: #cdd6f4;")
        self.tab_widget.addTab(welcome, "Welcome")

        layout.addWidget(self.tab_widget)

    def open_file_in_tab(self, file_path):
        if not file_path or not os.path.exists(file_path): return
        
        filename = os.path.basename(file_path)
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == filename:
                self.tab_widget.setCurrentIndex(i)
                return

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("background-color: #1a1b26; color: #d1d4e0; font-family: 'Consolas'; font-size: 12px;")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                text_edit.setText(content)
        except Exception as e:
            text_edit.setText(f"Error reading file: {e}")

        idx = self.tab_widget.addTab(text_edit, filename)
        self.tab_widget.setCurrentIndex(idx)

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)
