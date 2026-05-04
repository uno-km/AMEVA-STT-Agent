import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QTextEdit, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt
import csv

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

        # CSV 파일인 경우 테이블 뷰어로 생성
        if file_path.lower().endswith('.csv'):
            widget = self._create_csv_table(file_path)
        else:
            widget = self._create_text_viewer(file_path)

        idx = self.tab_widget.addTab(widget, filename)
        self.tab_widget.setCurrentIndex(idx)

    def _create_text_viewer(self, file_path):
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("background-color: #1a1b26; color: #d1d4e0; font-family: 'Consolas'; font-size: 12px; border: none;")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_edit.setText(f.read())
        except Exception as e:
            text_edit.setText(f"Error reading file: {e}")
        return text_edit

    def _create_csv_table(self, file_path):
        table = QTableWidget()
        table.setStyleSheet("""
            QTableWidget { 
                background-color: #1a1b26; 
                color: #d1d4e0; 
                gridline-color: #2e3c43; 
                border: none;
                font-size: 11px;
            }
            QHeaderView::section { 
                background-color: #2e3c43; 
                color: #88c0d0; 
                padding: 6px; 
                border: 1px solid #1a1b26;
                font-weight: bold;
            }
        """)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 콤마(,)와 파이프(|) 자동 감지 시도
                content = f.read(1024)
                f.seek(0)
                dialect = csv.Sniffer().sniff(content) if content else None
                reader = list(csv.reader(f, dialect=dialect if dialect else 'excel'))
                
                if not reader: return table
                
                table.setRowCount(len(reader))
                table.setColumnCount(len(reader[0]))
                
                for r_idx, row in enumerate(reader):
                    for c_idx, col in enumerate(row):
                        item = QTableWidgetItem(col)
                        table.setItem(r_idx, c_idx, item)
                
                # 헤더 설정 (첫 줄 기준)
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
                table.verticalHeader().setVisible(False)
        except Exception as e:
            error_label = QLabel(f"CSV 로드 실패: {e}")
            error_label.setStyleSheet("color: #bf616a; padding: 20px;")
            return error_label
            
        return table

    def close_tab(self, index):
        if self.tab_widget.count() > 1:
            self.tab_widget.removeTab(index)
