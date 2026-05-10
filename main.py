import sys
import os
import traceback
import multiprocessing

# Silence HuggingFace Hub warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["PYTHONWARNINGS"] = "ignore"

def main():
    try:
        multiprocessing.freeze_support()
        try:
            multiprocessing.set_start_method("spawn", force=True)
        except RuntimeError:
            pass # Already set or not supported
        
        print("2. Importing QApplication")
        from PyQt6.QtWidgets import QApplication
        print("3. Creating QApplication")
        app = QApplication(sys.argv)
        
        # Set default font to avoid legacy font issues (Fixedsys error)
        from PyQt6.QtGui import QFont
        font = QFont("Malgun Gothic", 10)
        app.setFont(font)
        
        print("4. Importing MainWindow")
        from gui.main_window import MainWindow
        
        print("5. Creating MainWindow")
        window = MainWindow()
        print("6. Showing MainWindow")
        window.show()
        print("7. Executing App")
        sys.exit(app.exec())
    except Exception as e:
        print(f"Exception: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
