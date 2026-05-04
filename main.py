import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication
from gui.main_window import MainWindow

def main():
    # Needed for Windows multiprocessing to work correctly when bundled
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
