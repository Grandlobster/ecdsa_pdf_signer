"""
main.py

Start the Signet desktop application:

    python main.py

The signing and verifying code lives in the "backend" folder and the
windows live in the "gui" folder. This file only connects them and opens the window.
"""

import os
import sys


# Make the backend and gui folders importable (works from source and when packaged).
if getattr(sys, "frozen", False):
    PROJECT_FOLDER = sys._MEIPASS
else:
    PROJECT_FOLDER = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, os.path.join(PROJECT_FOLDER, "backend"))
sys.path.insert(0, os.path.join(PROJECT_FOLDER, "gui"))


def run_self_test_and_exit():
    # "Signet --self-test" signs and verifies a PDF without opening a window.
    import self_test

    try:
        for line in self_test.run_self_test():
            print("OK  " + line)
    except Exception as error:
        print("SELF-TEST FAILED: " + str(error))
        sys.exit(1)

    print("Self-test passed.")
    sys.exit(0)


if "--self-test" in sys.argv:
    run_self_test_and_exit()

from PySide6.QtWidgets import QApplication

import folders
import theme
from main_window import MainWindow


def start_application():
    folders.make_sure_folders_exist()

    application = QApplication(sys.argv)
    application.setApplicationName("Signet")
    application.setStyle("Fusion")
    application.setFont(theme.make_font("sans", 14))
    application.setStyleSheet(theme.GLOBAL_STYLE_SHEET)

    window = MainWindow()
    window.show()

    return application.exec()


if __name__ == "__main__":
    sys.exit(start_application())
