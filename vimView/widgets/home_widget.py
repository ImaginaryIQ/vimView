from pathlib import Path
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QApplication
from PySide6.QtGui import QKeyEvent, QFont, QDesktopServices

from config import DEFAULT_DIR, CONFIG_FILE

class HomeWidget(QWidget):
    open_dir = Signal(Path)
    restore_session = Signal()   # new signal for space key

    def __init__(self, config: dict, app_font: str):
        super().__init__()
        self.config = config
        self.theme = config["theme"]
        self.app_font = app_font
        self.setFocusPolicy(Qt.StrongFocus)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(15)

        t_dim = self.theme["dim_text"]
        t_acc = self.theme["accent"]
        t_bg = self.theme["background"]
        t_txt = self.theme["text"]

        title = QLabel(
            f"<span style='color: {t_dim}'>vim</span>"
            f"<span style='color: {t_acc}'>v</span>"
            f"<span style='color: {t_dim}'>iew</span>"
        )
        title.setFont(QFont(self.app_font, 42, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setTextFormat(Qt.RichText)
        title.setStyleSheet("letter-spacing: 4px;")

        subtitle = QLabel("system ready.")
        subtitle.setFont(QFont(self.app_font, 11))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"color: {t_acc}; letter-spacing: 2px;")

        instructions = QLabel(
            # "<br>[ 1 ] Customi<br><br>"
            # "[ o ] select directory<br><br>"
            # "[ e ] edit config<br><br>"
            # "[ space ] restore last session<br><br>"
            # "[ q ] terminate<br>"
            "<br>~strip the noise. forge the aesthetic.<br><br>"
"~load the vision. execute.<br><br>"
"~master the system. dictate your environment.<br><br>"
"~resurrect the grind. do the work.<br><br>"
"~kill the process. keep the discipline.<br>"
        )
        instructions.setFont(QFont(self.app_font, 11, QFont.Bold))
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet(
            f"background-color: {t_bg}; color: {t_txt}; "
            f"padding: 20px 40px; border: 1px dotted {t_acc};"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(30)

        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(instructions)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        self.setStyleSheet(f"background-color: {t_bg};")

    def keyPressEvent(self, event: QKeyEvent):
        key = event.text().lower()
        if key == "v":
            self.open_dir.emit(DEFAULT_DIR)
        elif key == "o":
            folder = QFileDialog.getExistingDirectory(
                self, "select directory", str(Path.home()),
                QFileDialog.Options(QFileDialog.DontUseNativeDialog)
            )
            if folder:
                self.open_dir.emit(Path(folder))
        elif key == "e":
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_FILE)))
        elif key == " ":
            self.restore_session.emit()
        elif key == "q" or event.key() == Qt.Key_Escape:
            QApplication.quit()
