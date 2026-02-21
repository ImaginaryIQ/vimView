# 📷 vimview

[![One‑liner](https://img.shields.io/badge/install-one%E2%80%90liner-brightgreen)](#-one-line-installation)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A minimalist, keyboard‑driven image viewer inspired by Vim.  
Navigate through your images with Vim‑style keybindings, preview thumbnails, and never touch the mouse.

## ✨ Features

- **Vim‑style keybindings** – all actions are one key away.
- **Filmstrip** – thumbnail preview at the bottom.
- **Zoom & rotate** – inspect details with `i`, `c`, `w`, `[`, `]`.
- **Clipboard integration** – copy/cut images and file paths.
- **Search** – quickly filter images by filename (`s`).
- **Undo** – revert the last delete, move, or rename (`u`).
- **Quick folders** – define frequently used folders for one‑key moves.
- **Session restore** – press <kbd>space</kbd> on the home screen to return to your last viewed image.
- **Fully configurable** – keymap, quick folders, colors, and confirmation prompts via JSON.
- **Lightweight & fast** – pre‑built binary available, no Python/runtime dependencies needed.

---

## 🚀 One‑line Installation

Open a terminal and run:

```bash
curl -fsSL https://raw.githubusercontent.com/ImaginaryIQ/vimView/main/install.sh | bash
```

This command will:
- Download the latest version of vimview (pre‑built binary or source fallback).
- Install the binary to `~/.local/bin/vimview`.
- Add `~/.local/bin` to your `PATH` (if not already).
- Install an icon (if `icon.png` is present in the repository).
- Create a desktop entry so vimview appears in your application menu.

After installation, you can run `vimview` from any terminal or launch it from your desktop environment.

---

## 🖥️ Usage

Start the app:
```bash
vimview                 # opens home screen
vimview /path/to/folder # directly opens that folder
```

### Home screen keys
- `v` – open default `~/Pictures/Photo`
- `o` – choose a directory via file dialog
- `e` – edit configuration file
- `space` – restore last session (if any)
- `q` / `Esc` – quit

### Viewer keys (configurable, defaults shown)
| Key        | Action                     |
|------------|----------------------------|
| `h` / `l`  | previous / next image      |
| `j`        | toggle filmstrip           |
| `g`        | toggle filename overlay    |
| `y`        | copy image to clipboard    |
| `x`        | cut image to clipboard     |
| `t`        | copy file path             |
| `i` / `c`  | zoom in / out              |
| `w`        | reset zoom (real size)     |
| `[` / `]`  | rotate left / right        |
| `f`        | toggle fullscreen          |
| `d`        | trash current image        |
| `r`        | rename current file        |
| `a`        | quick move mode            |
| `m`        | move to custom folder      |
| `s`        | search by filename         |
| `u`        | undo last action           |
| `k`        | show keybindings           |
| `e`        | edit config                |
| `q` / `Esc`| go back to home            |

In **quick move mode** (`a`), press the key you assigned in `quick_folders` (default `b`/`n`) to move the current image to that folder.

In **search mode** (`s`), type a substring; suggestions appear below. Use arrow keys to navigate and <kbd>Enter</kbd> to jump directly.

---

## ⚙️ Configuration

The configuration file is stored at `~/.config/vimView/config.json`.  
If the file doesn't exist, it is created with the default settings.

You can edit it manually (press `e` from home or viewer) to customise:

```json
{
  "settings": {
    "require_confirmation": false,
    "show_filename": true
  },
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
    "quit": "q"
  },
  "quick_folders": {
    "b": "folder_1",
    "n": "folder_2"
  },
  "theme": {
    "accent": "#ea0000",
    "background": "#000000",
    "surface": "#050505",
    "text": "#ffffff",
    "dim_text": "#666666",
    "border": "#333333"
  }
}
```

- **settings.require_confirmation** – ask before delete/move/rename.
- **settings.show_filename** – show filename banner briefly when switching images.
- **keymap** – change any key (use single characters).
- **quick_folders** – map a key to a folder name (relative to the current directory). Press that key in quick move mode to move there.
- **theme** – customise colours (hex values).

After editing, restart the app for changes to take effect.

---

## 💾 Session Persistence

The app automatically saves your last viewed directory and image index when you:
- Press `q` in the viewer.
- Press `Esc` when at the first image (returning home).
- Close the application window.

From the **home screen**, press <kbd>space</kbd> to jump back to that exact image.

The session data is stored in `~/.config/vimView/session.json`.

---

## 🛠️ For Developers / Building from Source

If you prefer to run from source or want to contribute:

```bash
git clone https://github.com/ImaginaryIQ/vimView.git
cd vimView
pip install --user pyside6
python main.py
```

To build a standalone binary (requires PyInstaller):
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name vimview main.py
```

The binary will be created in `dist/vimview`.

---

## 🤝 Contributing

Bug reports, feature requests, and pull requests are welcome!  
Please open an issue on GitHub first to discuss any major changes.

---

## 📄 License

This project is licensed under the MIT License – see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- Inspired by the simplicity of Vim and the need for a mouse‑free image viewer.
- Uses the excellent [Qt for Python](https://www.qt.io/qt-for-python) (PySide6) framework.

---

**Enjoy your vim‑powered image browsing!**
