import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QStackedWidget, QMainWindow
from PySide6.QtGui import QFont

from config import load_config, load_session
from utils import load_custom_font
from widgets.home_widget import HomeWidget
from widgets.image_viewer import ImageViewerWidget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("vimview")
        self.resize(1100, 750)

        self.app_font = load_custom_font()
        self.config = load_config()
        self._apply_global_style()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.home_view = HomeWidget(self.config, self.app_font)
        self.viewer_view = ImageViewerWidget(self.config, self.app_font)

        self.stack.addWidget(self.home_view)
        self.stack.addWidget(self.viewer_view)

        self.home_view.open_dir.connect(self.switch_to_viewer)
        self.home_view.restore_session.connect(self.load_last_session)
        self.viewer_view.go_home.connect(self.switch_to_home)

        self.home_view.setFocus()

    def _apply_global_style(self):
        t_bg = self.config["theme"]["background"]
        t_txt = self.config["theme"]["text"]
        t_acc = self.config["theme"]["accent"]
        t_bord = self.config["theme"]["border"]

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {t_bg};
                color: {t_txt};
                font-family: "{self.app_font}";
            }}
            QScrollBar {{
                background: {t_bg};
                width: 8px;
            }}
            QScrollBar::handle {{
                background: {t_bord};
            }}
            QPushButton {{
                background-color: {t_bg};
                border: 1px dotted {t_txt};
                padding: 5px;
            }}
            QPushButton:hover {{
                border: 1px solid {t_acc};
                color: {t_acc};
            }}
        """)

    def switch_to_viewer(self, directory: Path):
        self.viewer_view.load_directory(directory)
        self.stack.setCurrentWidget(self.viewer_view)
        self.viewer_view.setFocus()

    def load_last_session(self):
        last_dir, last_index = load_session()
        if last_dir and last_dir.exists():
            self.viewer_view.load_directory(last_dir, last_index)
            self.stack.setCurrentWidget(self.viewer_view)
            self.viewer_view.setFocus()
        # else do nothing (stay on home screen)

    def switch_to_home(self):
        self.stack.setCurrentWidget(self.home_view)
        self.viewer_view.clean_up()
        self.setWindowTitle("vimview")
        self.home_view.setFocus()

    def closeEvent(self, event):
        self.viewer_view.clean_up()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()

    if len(sys.argv) > 1 and Path(sys.argv[1]).is_dir():
        window.switch_to_viewer(Path(sys.argv[1]))
    else:
        window.show()

    sys.exit(app.exec())
