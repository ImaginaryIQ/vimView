from pathlib import Path
from PySide6.QtGui import QFontDatabase

def load_custom_font() -> str:
    font_dir = Path.home() / ".local" / "share" / "fonts"
    if font_dir.exists():
        for font_file in font_dir.rglob("*"):
            if "dank" in font_file.name.lower() and "mono" in font_file.name.lower():
                font_id = QFontDatabase.addApplicationFont(str(font_file))
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        return families[0]
    return "monospace"
