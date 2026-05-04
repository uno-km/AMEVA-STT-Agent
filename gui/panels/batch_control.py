import os
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QHBoxLayout, QLabel, QSpinBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from src.core.settings_manager import settings_manager

class BatchControlPanel(QWidget):
    run_requested = pyqtSignal()
    file_clicked = pyqtSignal(str) # 파일 클릭 신호 추가

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_paths()
        
        # 주기적으로 로그 새로고침
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_log)
        self.refresh_timer.start(5000)

        # 자동 실행 타이머
        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.on_auto_timer_timeout)
        
        # 카운트다운 표시용 타이머 (1초 주기)
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown_label)
        self.remaining_seconds = 0

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("⏱️ 배치 관리자")
        title.setObjectName("title")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffcb6b; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # 경로 설정
        self.line_input = QLineEdit()
        btn_browse_in = QPushButton("...")
        btn_browse_in.setFixedWidth(40)
        btn_browse_in.clicked.connect(lambda: self.browse("input"))
        h1 = QHBoxLayout()
        h1.addWidget(self.line_input)
        h1.addWidget(btn_browse_in)
        form.addRow("입력 폴더:", h1)

        self.line_output = QLineEdit()
        btn_browse_out = QPushButton("...")
        btn_browse_out.setFixedWidth(40)
        btn_browse_out.clicked.connect(lambda: self.browse("output"))
        h2 = QHBoxLayout()
        h2.addWidget(self.line_output)
        h2.addWidget(btn_browse_out)
        form.addRow("출력 폴더:", h2)

        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 1440)
        self.spin_interval.setSuffix(" 분")
        self.spin_interval.valueChanged.connect(self.toggle_auto_mode) # 주기 변경 시 즉시 반영
        form.addRow("자동 주기:", self.spin_interval)

        self.label_countdown = QLabel("자동 모드 비활성")
        self.label_countdown.setStyleSheet("color: #8b949e; font-size: 11px; margin-left: 5px;")
        form.addRow("스케줄 상태:", self.label_countdown)

        self.check_auto = QCheckBox("자동 모드 활성화 (스케줄러)")
        self.check_auto.setStyleSheet("color: #a3be8c; font-weight: bold; margin-top: 5px;")
        self.check_auto.stateChanged.connect(self.toggle_auto_mode)
        form.addRow("", self.check_auto)

        layout.addLayout(form)

        # 버튼 영역
        btn_layout = QHBoxLayout()
        self.btn_save_path = QPushButton("💾 경로 저장")
        self.btn_save_path.setStyleSheet("background-color: #4f5b66; padding: 10px; font-weight: bold;")
        self.btn_save_path.clicked.connect(self.save_paths)
        
        self.btn_run_batch = QPushButton("🚀 배치 실행")
        self.btn_run_batch.setObjectName("btn_run_batch")
        self.btn_run_batch.setStyleSheet("background-color: #bf616a; padding: 10px; font-weight: bold;")
        
        btn_layout.addWidget(self.btn_save_path)
        btn_layout.addWidget(self.btn_run_batch)
        layout.addLayout(btn_layout)

        # 구분선
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #2e3c43; margin-top: 15px; margin-bottom: 10px;")
        layout.addWidget(line)

        # 배치 이력 테이블
        history_label = QLabel("📊 최근 배치 이력 (CSV)")
        history_label.setStyleSheet("font-weight: bold; color: #88c0d0; margin-bottom: 5px;")
        layout.addWidget(history_label)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["시간", "파일명", "상태", "소요"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1a1b26; gridline-color: #2e3c43; font-size: 11px; }
            QHeaderView::section { background-color: #2e3c43; color: white; padding: 4px; border: none; }
        """)
        self.table.itemClicked.connect(self.on_item_clicked) # 클릭 이벤트 연결
        layout.addWidget(self.table)
        
        self.refresh_log()

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
        self.check_auto.setChecked(b.get("auto_mode", False))
        # 초기 상태에 따라 타이머 설정
        if self.check_auto.isChecked():
            self.toggle_auto_mode()

    def save_paths(self):
        settings_manager.settings["batch"]["input_dir"] = self.line_input.text()
        settings_manager.settings["batch"]["output_dir"] = self.line_output.text()
        settings_manager.settings["batch"]["interval_min"] = self.spin_interval.value()
        settings_manager.settings["batch"]["auto_mode"] = self.check_auto.isChecked()
        settings_manager.save()
        self.toggle_auto_mode() # 타이머 갱신

    def toggle_auto_mode(self):
        if self.check_auto.isChecked():
            interval_min = self.spin_interval.value()
            interval_ms = interval_min * 60 * 1000
            self.auto_timer.start(interval_ms)
            self.remaining_seconds = interval_min * 60
            self.countdown_timer.start(1000)
            self.label_countdown.setText(f"다음 실행까지 {self.remaining_seconds}초 남음")
            self.run_requested.emit() # 활성화 즉시 첫 실행 요청
        else:
            self.auto_timer.stop()
            self.countdown_timer.stop()
            self.label_countdown.setText("자동 모드 비활성")

    def update_countdown_label(self):
        if self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.label_countdown.setText(f"다음 실행까지 {self.remaining_seconds}초 남음")
        else:
            self.remaining_seconds = self.spin_interval.value() * 60

    def on_auto_timer_timeout(self):
        if self.check_auto.isChecked():
            self.run_requested.emit()

    def refresh_log(self):
        db_file = settings_manager.get("batch").get("db_file", "stt_batch_log.csv")
        if not os.path.exists(db_file):
            return

        try:
            with open(db_file, "r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                rows = reader[-10:] # 최근 10개만 표시
                rows.reverse()
                
                self.table.setRowCount(len(rows))
                for i, row in enumerate(rows):
                    self.table.setItem(i, 0, QTableWidgetItem(row.get("timestamp", "")[5:])) # 날짜 앞부분 제외
                    self.table.setItem(i, 1, QTableWidgetItem(os.path.basename(row.get("original_filename", ""))))
                    status_item = QTableWidgetItem(row.get("status", ""))
                    if row.get("status") == "SUCCESS": status_item.setForeground(Qt.GlobalColor.green)
                    else: status_item.setForeground(Qt.GlobalColor.red)
                    self.table.setItem(i, 2, status_item)
                    self.table.setItem(i, 3, QTableWidgetItem(f"{row.get('duration', '0')}s"))
        except:
            pass

    def on_item_clicked(self, item):
        row = item.row()
        file_name = self.table.item(row, 1).text()
        self.file_clicked.emit(file_name)
