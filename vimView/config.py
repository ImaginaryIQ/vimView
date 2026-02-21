import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "vimView"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSION_FILE = CONFIG_DIR / "session.json"
DEFAULT_DIR = Path.home() / "Pictures" / "Photo"

DEFAULT_CONFIG = {
    "settings": {"require_confirmation": False, "show_filename": True},
    "keymap": {
        "next": "l",
        "prev": "h",
        "copy": "y",
        "cut": "x",
        "copy_path": "t",
        "zoom_in": "i",
        "zoom_out": "c",
        "zoom_real": "w",
        "delete": "d",
        "rename": "r",
        "move_mode": "a",
        "move_custom": "m",
        "search": "s",
        "toggle_filmstrip": "j",
        "toggle_filename": "g",
        "rotate_left": "[",
        "rotate_right": "]",
        "fullscreen": "f",
        "undo": "u",
        "show_keys": "k",
        "edit_config": "e",
        "quit": "q",
    },
    "quick_folders": {"b": "folder_1", "n": "folder_2"},
    "theme": {
        "accent": "#ea0000",
        "background": "#000000",
        "surface": "#050505",
        "text": "#ffffff",
        "dim_text": "#666666",
        "border": "#333333",
    },
}

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                data = json.load(f)
                merged = DEFAULT_CONFIG.copy()
                for key in merged:
                    if key in data and isinstance(data[key], dict):
                        merged[key].update(data[key])
                if "quick_folders" in data:
                    merged["quick_folders"] = data["quick_folders"]
                return merged
        except json.JSONDecodeError:
            pass
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG

def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def save_session(last_dir: Path | None, last_index: int = 0):
    """Save the last viewed directory and image index."""
    data = {}
    if last_dir:
        data["last_dir"] = str(last_dir)
        data["last_index"] = last_index
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f)

def load_session() -> tuple[Path | None, int]:
    """Return (last_dir Path or None, last_index)."""
    if not SESSION_FILE.exists():
        return None, 0
    try:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        if "last_dir" in data:
            p = Path(data["last_dir"])
            if p.exists() and p.is_dir():
                return p, data.get("last_index", 0)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return None, 0
