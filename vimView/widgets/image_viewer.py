import shutil
from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import (
    Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve,
    QEvent, QUrl, Signal, QMimeData
)
from PySide6.QtGui import (
    QKeyEvent, QPixmap, QFont, QIcon, QImageReader, QDesktopServices,
    QTransform, QImage, QClipboard
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QListWidget,
    QListWidgetItem, QLineEdit, QFileDialog, QGraphicsOpacityEffect,
    QApplication
)

from config import save_config, save_session, CONFIG_FILE
from workers.thumbnail_worker import ThumbnailWorker

class ViewerMode(Enum):
    NORMAL = auto()
    CONFIRM = auto()
    QUICK_MOVE = auto()
    RENAME = auto()
    SEARCH = auto()

class ImageViewerWidget(QWidget):
    go_home = Signal()

    def __init__(self, config: dict, app_font: str):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)

        self.config = config
        self.keymap = {k: v.lower() for k, v in config["keymap"].items()}
        self.theme = config["theme"]
        self.settings = config["settings"]
        self.folders = {k.lower(): v for k, v in config["quick_folders"].items()}
        self.app_font = app_font

        self.directory: Path | None = None
        self.all_image_files: list[Path] = []
        self.image_files: list[Path] = []          # filtered list
        self.thumb_cache: dict[str, QPixmap] = {}
        self.filmstrip_item_map: dict[Path, QListWidgetItem] = {}

        self.current_index = 0
        self.rotation_angle = 0
        self.zoom_mode = "fit"      # "fit" or "custom"
        self.zoom_factor = 1.0
        self.worker: ThumbnailWorker | None = None
        self.undo_stack: list[dict] = []

        self.mode = ViewerMode.NORMAL
        self.confirm_callback = None
        self.is_search_filtered = False
        self.pre_search_path: Path | None = None
        self.trash_dir: Path | None = None

        self._setup_ui()
        self._setup_timers()

    # ----------------------------------------------------------------------
    # UI setup
    # ----------------------------------------------------------------------
    def _setup_ui(self):
        t_bg = self.theme["background"]
        t_surf = self.theme["surface"]
        t_txt = self.theme["text"]
        t_acc = self.theme["accent"]
        t_bord = self.theme["border"]

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Scroll area with image label
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet(f"background-color: {t_bg}; border: none;")

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"background-color: {t_bg}; color: {t_txt};")
        self.scroll_area.setWidget(self.label)

        # Top overlay (filename)
        self.top_overlay = QLabel(self.scroll_area)
        self.top_overlay.setStyleSheet(
            f"background-color: rgba(0,0,0,200); color: {t_txt}; "
            f"padding: 8px 16px; border-bottom: 1px dotted {t_bord};"
        )
        self.top_overlay.setFont(QFont(self.app_font, 10))
        self.top_overlay.setAlignment(Qt.AlignCenter)
        self.top_overlay.hide()

        # Central overlay (notifications / confirmations)
        self.overlay = QLabel(self.scroll_area)
        self.overlay.setStyleSheet(
            f"background-color: rgba(0,0,0,240); color: {t_acc}; "
            f"padding: 20px 30px; border: 1px dotted {t_acc};"
        )
        self.overlay.setFont(QFont(self.app_font, 11, QFont.Bold))
        self.overlay.setAlignment(Qt.AlignCenter)
        self.overlay.hide()

        self.opacity_effect = QGraphicsOpacityEffect(self.overlay)
        self.overlay.setGraphicsEffect(self.opacity_effect)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(150)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)

        # Input container (rename / search)
        self.input_container = QWidget(self.scroll_area)
        self.input_container.setStyleSheet(
            f"background-color: rgba(0,0,0,240); border: 1px solid {t_acc}; padding: 10px;"
        )
        input_layout = QVBoxLayout(self.input_container)

        self.input_prompt = QLabel()
        self.input_prompt.setFont(QFont(self.app_font, 11, QFont.Bold))
        self.input_prompt.setStyleSheet(f"color: {t_acc}; border: none;")

        self.text_input = QLineEdit()
        self.text_input.setFont(QFont(self.app_font, 11))
        self.text_input.setStyleSheet(
            f"background-color: {t_bg}; color: {t_txt}; "
            f"border: 1px dotted {t_bord}; padding: 5px;"
        )
        self.text_input.returnPressed.connect(self._process_text_input)
        self.text_input.installEventFilter(self)
        self.text_input.textChanged.connect(self._on_search_text_changed)

        input_layout.addWidget(self.input_prompt)
        input_layout.addWidget(self.text_input)
        self.input_container.hide()

        # Suggestion list (for search)
        self.suggestion_list = QListWidget(self.scroll_area)
        self.suggestion_list.setIconSize(QSize(36, 36))
        self.suggestion_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.suggestion_list.setStyleSheet(
            f"""
            QListWidget {{
                background-color: rgba(0,0,0,240);
                border: 1px solid {t_acc};
                border-top: none;
                color: {t_txt};
                font-family: "{self.app_font}";
                font-size: 10pt;
            }}
            QListWidget::item {{ padding: 5px; border-bottom: 1px dotted {t_bord}; }}
            QListWidget::item:selected {{ background-color: {t_acc}; color: #000000; }}
            """
        )
        self.suggestion_list.hide()
        self.suggestion_list.itemActivated.connect(self._on_suggestion_activated)

        # Filmstrip
        self.filmstrip = QListWidget()
        self.filmstrip.setFlow(QListWidget.LeftToRight)
        self.filmstrip.setFixedHeight(120)
        self.filmstrip.setIconSize(QSize(90, 90))
        self.filmstrip.setSpacing(8)
        self.filmstrip.setFocusPolicy(Qt.NoFocus)
        self.filmstrip.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {t_surf};
                border-top: 1px dashed {t_bord};
                padding: 10px;
            }}
            QListWidget::item {{
                background-color: {t_bg};
                border: 1px solid {t_bord};
            }}
            QListWidget::item:selected {{
                background-color: {t_bg};
                border: 1px solid {t_acc};
            }}
            """
        )
        self.filmstrip.currentRowChanged.connect(self._on_filmstrip_selected)

        self.layout.addWidget(self.scroll_area)
        self.layout.addWidget(self.filmstrip)

    def _setup_timers(self):
        self.overlay_timer = QTimer(self)
        self.overlay_timer.setSingleShot(True)
        self.overlay_timer.timeout.connect(self._hide_notification_overlay)

        self.filename_timer = QTimer(self)
        self.filename_timer.setSingleShot(True)
        self.filename_timer.timeout.connect(self._hide_filename_overlay)

    # ----------------------------------------------------------------------
    # Directory loading
    # ----------------------------------------------------------------------
    def load_directory(self, directory: Path, initial_index: int = 0):
        self.directory = Path(directory).resolve()
        self.undo_stack.clear()
        self.thumb_cache.clear()
        self.is_search_filtered = False
        self.pre_search_path = None

        self.trash_dir = self.directory / ".vimview_trash"
        self.trash_dir.mkdir(exist_ok=True)

        self.all_image_files = self._get_images()
        self.image_files = list(self.all_image_files)

        if self.image_files:
            self.current_index = max(0, min(initial_index, len(self.image_files) - 1))
        else:
            self.current_index = 0

        self.rotation_angle = 0
        self.zoom_mode = "fit"
        self.zoom_factor = 1.0
        self.mode = ViewerMode.NORMAL

        self._rebuild_filmstrip_and_thumbnails()

    def _get_images(self) -> list[Path]:
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        if not self.directory or not self.directory.is_dir():
            return []
        return sorted(
            p for p in self.directory.iterdir()
            if p.suffix.lower() in exts and not p.name.startswith(".")
        )

    # ----------------------------------------------------------------------
    # Filmstrip & thumbnails
    # ----------------------------------------------------------------------
    def _rebuild_filmstrip_and_thumbnails(self):
        # Stop previous worker
        if self.worker:
            self.worker.stop()
            self.worker.wait()

        self.filmstrip.clear()
        self.filmstrip_item_map.clear()

        # Create empty items
        for img_path in self.image_files:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, str(img_path))
            self.filmstrip.addItem(item)
            self.filmstrip_item_map[img_path] = item

        self._update_image()

        # Start loading thumbnails
        if self.image_files:
            self.worker = ThumbnailWorker(self.image_files)
            self.worker.icon_ready.connect(self._apply_thumbnail)
            self.worker.start()

    def _apply_thumbnail(self, path_str: str, pixmap: QPixmap):
        path = Path(path_str)
        # Only apply if the path is still in the current map
        item = self.filmstrip_item_map.get(path)
        if item is not None:
            item.setIcon(QIcon(pixmap))
            self.thumb_cache[path_str] = pixmap

    # ----------------------------------------------------------------------
    # Image display
    # ----------------------------------------------------------------------
    def _update_image(self):
        self.rotation_angle = 0
        self.zoom_mode = "fit"
        self.zoom_factor = 1.0

        if not self.image_files:
            self.label.setText("no images found")
            self.label.setFont(QFont(self.app_font, 12))
            self.window().setWindowTitle("vimview - empty")
            self.filmstrip.hide()
            self.original_pixmap = None
            return

        if not self.filmstrip.isHidden():
            self.filmstrip.show()

        self.current_index = max(0, min(self.current_index, len(self.image_files) - 1))
        img_path = self.image_files[self.current_index]

        self.original_pixmap = QPixmap(str(img_path))
        self._refresh_pixmap_scale()

        # Update filmstrip selection
        self.filmstrip.blockSignals(True)
        self.filmstrip.setCurrentRow(self.current_index)
        current_item = self.filmstrip.item(self.current_index)
        if current_item:
            self.filmstrip.scrollToItem(current_item, QListWidget.PositionAtCenter)
        self.filmstrip.blockSignals(False)

        self._update_title()
        self._trigger_filename_overlay(img_path.name)

    def _refresh_pixmap_scale(self):
        if not self.original_pixmap or self.original_pixmap.isNull():
            return

        transform = QTransform().rotate(self.rotation_angle)
        rotated = self.original_pixmap.transformed(transform, Qt.SmoothTransformation)

        if self.zoom_mode == "fit":
            target = self.scroll_area.viewport().size()
            scaled = rotated.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setFixedSize(scaled.size())
            self.label.setPixmap(scaled)
        else:
            target = rotated.size() * self.zoom_factor
            scaled = rotated.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.label.setFixedSize(target)
            self.label.setPixmap(scaled)

    def _update_title(self, status: str = ""):
        if not self.image_files:
            return
        img_path = self.image_files[self.current_index]
        title = f"vimview :: [{self.current_index+1}/{len(self.image_files)}] {img_path.name}"
        if self.zoom_mode == "custom":
            title += f" [zoom: {int(self.zoom_factor*100)}%]"
        if self.is_search_filtered:
            title += " [filtered]"
        if status:
            title += f" :: {status}"
        self.window().setWindowTitle(title)

    # ----------------------------------------------------------------------
    # Overlays & animations
    # ----------------------------------------------------------------------
    def _trigger_filename_overlay(self, name: str):
        if self.settings["show_filename"]:
            self.top_overlay.setText(name)
            self.top_overlay.adjustSize()
            self._position_overlays()
            self.top_overlay.show()
            self.filename_timer.start(1500)

    def _hide_filename_overlay(self):
        self.top_overlay.hide()

    def show_animated_overlay(self, text: str, auto_hide: bool = True):
        self.overlay.setText(text)
        self.overlay.adjustSize()
        self._position_overlays()
        self.overlay.show()
        self.anim.start()
        if auto_hide:
            self.overlay_timer.start(1500)
        else:
            self.overlay_timer.stop()

    def _hide_notification_overlay(self):
        self.overlay.hide()
        if self.mode == ViewerMode.CONFIRM:
            self.mode = ViewerMode.NORMAL

    def _position_overlays(self):
        if self.top_overlay.isVisible():
            x = (self.scroll_area.width() - self.top_overlay.width()) // 2
            self.top_overlay.move(x, 0)
        if self.overlay.isVisible():
            x = (self.scroll_area.width() - self.overlay.width()) // 2
            y = (self.scroll_area.height() - self.overlay.height()) // 2
            self.overlay.move(x, y)
        if self.input_container.isVisible():
            x = (self.scroll_area.width() - self.input_container.width()) // 2
            y = (self.scroll_area.height() - self.input_container.height()) // 2
            self.input_container.move(x, y)
        if self.suggestion_list.isVisible():
            self.suggestion_list.move(
                self.input_container.x(),
                self.input_container.y() + self.input_container.height()
            )

    # ----------------------------------------------------------------------
    # Actions (copy, delete, rename, move, undo, search)
    # ----------------------------------------------------------------------
    def _handle_action_request(self, prompt: str, callback, success_msg: str):
        if self.settings.get("require_confirmation", False):
            self.mode = ViewerMode.CONFIRM
            self.confirm_callback = callback
            full_text = f"{prompt}\n\n[enter] confirm  |  [space] cancel"
            self.show_animated_overlay(full_text, auto_hide=False)
            self._update_title("awaiting confirmation")
        else:
            callback()
            self.show_animated_overlay(success_msg)

    def _clipboard_action(self, action_type: str):
        if not self.image_files:
            return
        img_path = self.image_files[self.current_index]
        clipboard = QApplication.clipboard()

        if action_type == "copy_path":
            clipboard.setText(str(img_path.absolute()))
            self.show_animated_overlay("path copied to clipboard")
            return

        url = QUrl.fromLocalFile(str(img_path))
        mime = QMimeData()
        mime.setUrls([url])
        mime.setImageData(QImage(str(img_path)))

        gnome_format = b"copy\n" if action_type == "copy" else b"cut\n"
        gnome_format += url.toString().encode("utf-8")
        mime.setData("x-special/gnome-copied-files", gnome_format)

        clipboard.setMimeData(mime)
        self.show_animated_overlay(f"{action_type} to clipboard")

    def _open_text_input(self, mode: ViewerMode):
        self.mode = mode
        self.overlay.hide()

        if mode == ViewerMode.RENAME:
            self.input_prompt.setText("new file name:")
            current_name = self.image_files[self.current_index].stem
            self.text_input.setText(current_name)
        elif mode == ViewerMode.SEARCH:
            if not self.is_search_filtered and self.image_files:
                self.pre_search_path = self.image_files[self.current_index]
            self.input_prompt.setText("search filename:")
            self.text_input.clear()

        self.text_input.selectAll()
        self.input_container.adjustSize()
        self._position_overlays()
        self.input_container.show()
        self.text_input.setFocus()

    def _process_text_input(self):
        text = self.text_input.text().strip()
        mode = self.mode
        self.input_container.hide()
        self.suggestion_list.hide()
        self.setFocus()
        self.mode = ViewerMode.NORMAL

        if mode == ViewerMode.RENAME and text:
            self._handle_action_request(
                f"rename to '{text}'?",
                lambda: self._rename_current_file(text),
                f"renamed: {text}"
            )
        elif mode == ViewerMode.SEARCH:
            if self.suggestion_list.currentRow() >= 0:
                selected = self.suggestion_list.currentItem().data(Qt.UserRole)
                self._jump_to_image(Path(selected))
            elif not text:
                self._clear_search_filter()
            else:
                matches = [f for f in self.all_image_files if text.lower() in f.name.lower()]
                if not matches:
                    self.show_animated_overlay("no matches found")
                    return
                self.image_files = matches
                self.is_search_filtered = True
                self.current_index = 0
                self._rebuild_filmstrip_and_thumbnails()
                self.show_animated_overlay(f"filtered: {len(matches)} images")

    def _on_search_text_changed(self, text: str):
        if self.mode != ViewerMode.SEARCH:
            return
        text = text.strip().lower()
        if not text:
            self.suggestion_list.hide()
            return

        matches = [f for f in self.all_image_files if text in f.name.lower()][:6]
        if not matches:
            self.suggestion_list.hide()
            return

        self.suggestion_list.clear()
        for f in matches:
            item = QListWidgetItem(f.name)
            item.setData(Qt.UserRole, str(f))
            if str(f) in self.thumb_cache:
                item.setIcon(QIcon(self.thumb_cache[str(f)]))
            else:
                # quick thumbnail for suggestion
                reader = QImageReader(str(f))
                reader.setScaledSize(QSize(40, 40))
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img)
                    self.thumb_cache[str(f)] = pix
                    item.setIcon(QIcon(pix))
            self.suggestion_list.addItem(item)

        self.suggestion_list.setCurrentRow(-1)
        self.suggestion_list.resize(
            self.input_container.width(),
            min(250, self.suggestion_list.sizeHintForRow(0) * len(matches) + 10)
        )
        self._position_overlays()
        self.suggestion_list.show()

    def _on_suggestion_activated(self, item: QListWidgetItem):
        path_str = item.data(Qt.UserRole)
        self.input_container.hide()
        self.suggestion_list.hide()
        self.setFocus()
        self._jump_to_image(Path(path_str))

    def _jump_to_image(self, target: Path):
        if self.is_search_filtered:
            self.image_files = list(self.all_image_files)
            self.is_search_filtered = False
            self._rebuild_filmstrip_and_thumbnails()

        if target in self.image_files:
            self.current_index = self.image_files.index(target)
            self._update_image()
            self.show_animated_overlay(f"jumped to:\n{target.name}")

    def _clear_search_filter(self, show_msg: bool = True):
        if not self.is_search_filtered:
            return
        self.image_files = list(self.all_image_files)
        self.is_search_filtered = False

        if self.pre_search_path and self.pre_search_path in self.image_files:
            self.current_index = self.image_files.index(self.pre_search_path)
            self.pre_search_path = None
        else:
            self.current_index = 0

        self._rebuild_filmstrip_and_thumbnails()
        if show_msg:
            self.show_animated_overlay("search cleared\nreturned to gallery")

    # ----------------------------------------------------------------------
    # File operations
    # ----------------------------------------------------------------------
    def _rename_current_file(self, new_name: str):
        img_path = self.image_files[self.current_index]
        if not Path(new_name).suffix:
            new_name += img_path.suffix
        new_path = img_path.parent / new_name

        if new_path.exists():
            self.show_animated_overlay("error: file exists")
            return

        try:
            img_path.rename(new_path)

            # Update lists
            self.image_files[self.current_index] = new_path
            if img_path in self.all_image_files:
                idx = self.all_image_files.index(img_path)
                self.all_image_files[idx] = new_path

            # Update filmstrip item
            item = self.filmstrip.item(self.current_index)
            item.setData(Qt.UserRole, str(new_path))
            self.filmstrip_item_map.pop(img_path, None)
            self.filmstrip_item_map[new_path] = item

            # Update thumbnail cache
            if str(img_path) in self.thumb_cache:
                self.thumb_cache[str(new_path)] = self.thumb_cache.pop(str(img_path))

            self.undo_stack.append({
                "action": "rename_inplace",
                "old_path": img_path,
                "new_path": new_path,
                "index": self.current_index
            })
            self._update_image()
        except Exception as e:
            print(f"failed to rename: {e}")

    def _move_to_target(self, target_folder: Path):
        img_path = self.image_files[self.current_index]
        target_folder.mkdir(parents=True, exist_ok=True)

        new_path = target_folder / img_path.name
        counter = 1
        while new_path.exists():
            new_path = target_folder / f"{img_path.stem}_{counter}{img_path.suffix}"
            counter += 1

        try:
            shutil.move(str(img_path), str(new_path))
            self.undo_stack.append({
                "action": "move",
                "old_path": img_path,
                "new_path": new_path,
                "index": self.current_index
            })
            self._remove_item_from_view(self.current_index)
        except Exception as e:
            print(f"failed to move: {e}")

    def _delete_current(self):
        img_path = self.image_files[self.current_index]
        trash_path = self.trash_dir / img_path.name

        # handle name collision in trash
        counter = 1
        while trash_path.exists():
            trash_path = self.trash_dir / f"{img_path.stem}_{counter}{img_path.suffix}"
            counter += 1

        try:
            shutil.move(str(img_path), str(trash_path))
            self.undo_stack.append({
                "action": "delete",
                "old_path": img_path,
                "trash_path": trash_path,
                "index": self.current_index
            })
            self._remove_item_from_view(self.current_index)
        except Exception as e:
            print(f"failed to trash: {e}")

    def _remove_item_from_view(self, index: int):
        self.filmstrip.blockSignals(True)
        img_path = self.image_files.pop(index)

        if img_path in self.all_image_files:
            self.all_image_files.remove(img_path)

        self.filmstrip.takeItem(index)
        self.filmstrip_item_map.pop(img_path, None)
        self.filmstrip.blockSignals(False)

        self._update_image()

    def _undo_last_action(self):
        if not self.undo_stack:
            self.show_animated_overlay("no history to undo")
            return

        action = self.undo_stack.pop()
        index = action["index"]

        try:
            if action["action"] == "rename_inplace":
                action["new_path"].rename(action["old_path"])

                # Update lists
                self.image_files[index] = action["old_path"]
                if action["new_path"] in self.all_image_files:
                    m_idx = self.all_image_files.index(action["new_path"])
                    self.all_image_files[m_idx] = action["old_path"]

                # Update filmstrip item
                item = self.filmstrip.item(index)
                item.setData(Qt.UserRole, str(action["old_path"]))
                self.filmstrip_item_map.pop(action["new_path"], None)
                self.filmstrip_item_map[action["old_path"]] = item

                # Update thumbnail cache
                if str(action["new_path"]) in self.thumb_cache:
                    self.thumb_cache[str(action["old_path"])] = self.thumb_cache.pop(str(action["new_path"]))

                self._update_image()
                self.show_animated_overlay("undo: rename reverted")
                return

            elif action["action"] == "move":
                shutil.move(str(action["new_path"]), str(action["old_path"]))
            elif action["action"] == "delete":
                shutil.move(str(action["trash_path"]), str(action["old_path"]))

            # Re-insert into lists
            self.image_files.insert(index, action["old_path"])
            if action["old_path"] not in self.all_image_files:
                self.all_image_files.append(action["old_path"])

            # Recreate filmstrip item
            item = QListWidgetItem()
            item.setData(Qt.UserRole, str(action["old_path"]))
            self.filmstrip.insertItem(index, item)
            self.filmstrip_item_map[action["old_path"]] = item

            # Load thumbnail if available
            if str(action["old_path"]) in self.thumb_cache:
                item.setIcon(QIcon(self.thumb_cache[str(action["old_path"])]))
            else:
                # attempt to load quickly
                reader = QImageReader(str(action["old_path"]))
                reader.setScaledSize(QSize(100, 100))
                img = reader.read()
                if not img.isNull():
                    pix = QPixmap.fromImage(img)
                    self.thumb_cache[str(action["old_path"])] = pix
                    item.setIcon(QIcon(pix))

            self.current_index = index
            self._update_image()
            self.show_animated_overlay("undo: file restored")

        except Exception as e:
            print(f"undo failed: {e}")

    # ----------------------------------------------------------------------
    # Session persistence
    # ----------------------------------------------------------------------
    def _save_current_session(self):
        if self.directory and self.image_files:
            save_session(self.directory, self.current_index)

    # ----------------------------------------------------------------------
    # Event handling
    # ----------------------------------------------------------------------
    def eventFilter(self, obj, event):
        if obj == self.text_input and event.type() == QEvent.KeyPress:
            key = event.key()
            if self.mode == ViewerMode.SEARCH and self.suggestion_list.isVisible():
                if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
                    # forward navigation keys to the list
                    QApplication.sendEvent(self.suggestion_list, event)
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        if self.image_files and self.zoom_mode == "fit":
            self._refresh_pixmap_scale()
        self._position_overlays()
        super().resizeEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.text().lower()

        # --- Global Escape handling ---
        if event.key() == Qt.Key_Escape:
            if self.input_container.isVisible():
                self.input_container.hide()
                self.suggestion_list.hide()
                self.setFocus()
                self.mode = ViewerMode.NORMAL
                self.pre_search_path = None
                return
            if self.overlay.isVisible() or self.mode != ViewerMode.NORMAL:
                self.overlay.hide()
                self.mode = ViewerMode.NORMAL
                self._update_title()
                return
            if self._escape_or_back():
                return
            self._save_current_session()
            self.go_home.emit()
            return

        if event.key() == Qt.Key_Space and self.mode not in (ViewerMode.RENAME, ViewerMode.SEARCH):
            if self.overlay.isVisible() or self.mode != ViewerMode.NORMAL:
                self.overlay.hide()
                self.mode = ViewerMode.NORMAL
                self._update_title()
                return
            if self._escape_or_back():
                return

        # --- Confirmation mode ---
        if self.mode == ViewerMode.CONFIRM:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.overlay.hide()
                self.mode = ViewerMode.NORMAL
                if self.confirm_callback:
                    self.confirm_callback()
            return

        # --- Quick move mode ---
        if self.mode == ViewerMode.QUICK_MOVE:
            if key in self.folders:
                folder_name = self.folders[key]
                target = self.directory / folder_name
                self._handle_action_request(
                    f"move to '{folder_name}'?",
                    lambda: self._move_to_target(target),
                    f"moved to {folder_name}"
                )
            return

        # --- Quit / go home ---
        if key == self.keymap["quit"]:
            if self._escape_or_back():
                return
            self._save_current_session()
            self.go_home.emit()
            return

        # --- Commands that require images ---
        if not self.image_files and key not in (self.keymap["undo"], self.keymap["search"]):
            return

        # --- Normal mode keybindings ---
        if key == self.keymap["prev"]:
            self.current_index = max(0, self.current_index - 1)
            self._update_image()
        elif key == self.keymap["next"]:
            self.current_index = min(len(self.image_files) - 1, self.current_index + 1)
            self._update_image()
        elif key == self.keymap["toggle_filmstrip"]:
            self.filmstrip.setVisible(not self.filmstrip.isVisible())
        elif key == self.keymap["toggle_filename"]:
            self.settings["show_filename"] = not self.settings["show_filename"]
            self.config["settings"] = self.settings
            save_config(self.config)
            state = "on" if self.settings["show_filename"] else "off"
            self.show_animated_overlay(f"filename overlay: {state}")
        elif key == self.keymap["copy"]:
            self._clipboard_action("copy")
        elif key == self.keymap["cut"]:
            self._clipboard_action("cut")
        elif key == self.keymap["copy_path"]:
            self._clipboard_action("copy_path")
        elif key == self.keymap["zoom_in"]:
            self.zoom_mode = "custom"
            self.zoom_factor *= 1.25
            self._refresh_pixmap_scale()
            self._update_title()
        elif key == self.keymap["zoom_out"]:
            self.zoom_mode = "custom"
            self.zoom_factor /= 1.25
            self._refresh_pixmap_scale()
            self._update_title()
        elif key == self.keymap["zoom_real"]:
            self.zoom_mode = "custom"
            self.zoom_factor = 1.0
            self._refresh_pixmap_scale()
            self._update_title()
        elif key == self.keymap["rotate_left"]:
            self.rotation_angle = (self.rotation_angle - 90) % 360
            self._refresh_pixmap_scale()
        elif key == self.keymap["rotate_right"]:
            self.rotation_angle = (self.rotation_angle + 90) % 360
            self._refresh_pixmap_scale()
        elif key == self.keymap["fullscreen"]:
            if self.window().isFullScreen():
                self.window().showNormal()
            else:
                self.window().showFullScreen()
        elif key == self.keymap["delete"]:
            self._handle_action_request("trash current image?", self._delete_current, "file trashed")
        elif key == self.keymap["rename"]:
            self._open_text_input(ViewerMode.RENAME)
        elif key == self.keymap["search"]:
            self._open_text_input(ViewerMode.SEARCH)
        elif key == self.keymap["move_mode"]:
            self.mode = ViewerMode.QUICK_MOVE
            folder_list = "   ".join(f"[ {k} ] {v}" for k, v in self.folders.items())
            self.show_animated_overlay(
                f"quick move:\n\n{folder_list}\n\n[space] cancel",
                auto_hide=False
            )
            self._update_title("awaiting quick move target")
        elif key == self.keymap["move_custom"]:
            folder = QFileDialog.getExistingDirectory(
                self, "select destination", str(self.directory),
                QFileDialog.Options(QFileDialog.DontUseNativeDialog)
            )
            if folder:
                dest = Path(folder)
                self._handle_action_request(
                    f"move to '{dest.name}'?",
                    lambda: self._move_to_target(dest),
                    f"moved to {dest.name}"
                )
            self.setFocus()
        elif key == self.keymap["undo"]:
            self._undo_last_action()
        elif key == self.keymap["show_keys"]:
            self._toggle_keymap_overlay()
        elif key == self.keymap["edit_config"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(CONFIG_FILE)))
            self.show_animated_overlay("config opened.\nrestart app after saving.")

    def _escape_or_back(self) -> bool:
        """Handle Escape/Space when not in input mode. Returns True if action taken."""
        if self.is_search_filtered:
            self._clear_search_filter()
            return True
        if self.pre_search_path is not None:
            if self.pre_search_path in self.image_files:
                self.current_index = self.image_files.index(self.pre_search_path)
            else:
                self.current_index = 0
            self.pre_search_path = None
            self._update_image()
            self.show_animated_overlay("returned to previous image")
            return True
        return False

    def _toggle_keymap_overlay(self):
        if self.overlay.isVisible() and "keybindings" in self.overlay.text():
            self._hide_notification_overlay()
        else:
            self.mode = ViewerMode.CONFIRM  # just to keep overlay persistent
            km = self.keymap
            text = (
                "--- keybindings ---\n\n"
                f"{km['search']} : search filename\n"
                f"{km['next']} : next image\n"
                f"{km['prev']} : prev image\n"
                f"{km['zoom_in']} / {km['zoom_out']} : zoom in/out\n"
                f"{km['zoom_real']} : real size\n"
                f"{km['copy']} / {km['cut']} : copy/cut image\n"
                f"{km['copy_path']} : copy file path\n"
                f"{km['rotate_left']} / {km['rotate_right']} : rotate\n"
                f"{km['fullscreen']} : fullscreen\n"
                f"{km['toggle_filmstrip']} : preview strip\n"
                f"{km['toggle_filename']} : name banner\n"
                f"{km['move_mode']} : quick move folder\n"
                f"{km['move_custom']} : custom folder move\n"
                f"{km['rename']} : rename file\n"
                f"{km['delete']} : trash file\n"
                f"{km['undo']} : undo\n"
                f"{km['edit_config']} : edit config\n"
                f"{km['quit']} : go home\n"
            )
            self.show_animated_overlay(text, auto_hide=False)

    def _on_filmstrip_selected(self, index: int):
        if index >= 0:
            self.current_index = index
            self._update_image()

    def clean_up(self):
        self._save_current_session()
        if self.worker:
            self.worker.stop()
            self.worker.wait()
