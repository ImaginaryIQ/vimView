from PySide6.QtCore import QThread, Signal, QMutex, QSize
from PySide6.QtGui import QImageReader, QPixmap

class ThumbnailWorker(QThread):
    icon_ready = Signal(str, QPixmap)  # path as string, pixmap

    def __init__(self, image_paths: list):
        super().__init__()
        self.image_paths = list(image_paths)
        self._is_running = True
        self._mutex = QMutex()

    def run(self):
        for img_path in self.image_paths:
            self._mutex.lock()
            running = self._is_running
            self._mutex.unlock()
            if not running:
                break

            reader = QImageReader(str(img_path))
            reader.setScaledSize(QSize(100, 100))
            img = reader.read()
            if not img.isNull():
                pix = QPixmap.fromImage(img)
                self.icon_ready.emit(str(img_path), pix)

    def stop(self):
        self._mutex.lock()
        self._is_running = False
        self._mutex.unlock()
