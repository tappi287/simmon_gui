import logging
from multiprocessing import Pool, Queue
from pathlib import Path, WindowsPath
from queue import Empty
from threading import Thread
from typing import Optional

from qtpy.QtCore import QObject, Signal
from qtpy.QtGui import QImage, QImageWriter, QPixmap

from modules.extracticon import get_executable_icon
from shared_modules.globals import ICON_DIR, get_settings_dir


class GetIconSignals(QObject):
    pixmap = Signal(str, QPixmap)

    def __init__(self, ui):
        super(GetIconSignals, self).__init__(ui)


class IconReceiverThread(Thread):
    icon_files = dict()

    def __init__(self, ui, exit_event, log_queue):
        super(IconReceiverThread, self).__init__()
        self.signal_obj = GetIconSignals(ui)
        self.pixmap_signal = self.signal_obj.pixmap

        self.exit_event = exit_event
        self.receive_icon_queue = Queue()
        self.log_queue = log_queue
        self.orders = set()

    def run(self) -> None:
        logging.debug('Icon Receiver Thread starting.')
        self._get_icon_files_from_disk()

        while not self.exit_event.is_set():
            # -- Work down ordered Icons --
            current_order = None
            if self.orders:
                current_order = self.orders.pop()

                if self._get_existing_icon(current_order):
                    # Icon found and QPixmap emitted
                    continue

            if not current_order:
                self.exit_event.wait(1)
                continue

            # -- Extract Icon's --
            try:
                with Pool(processes=2) as pool:
                    img_data = pool.apply(get_executable_icon, (current_order, ))
            except Empty:
                continue

            # -- Write and emit result --
            if img_data is not None:
                # -- Create and store QImage
                img = QImage.fromData(img_data)
                if img.width() == 0:
                    logging.debug('Skipping empty extracted Exe Icon: %s', current_order.name)
                    continue

                self._write_image(current_order.name, img)
                self.icon_files[current_order.name] = img

                # -- Create and emit QPixmap --
                q_pixmap = QPixmap.fromImage(img)
                logging.debug('Get icon thread received: %s icon with size %s',
                              current_order.name, q_pixmap.size())
                self.pixmap_signal.emit(current_order.name, q_pixmap)

        logging.info('Icon Receiver Thread exiting')

    @staticmethod
    def _write_image(exe_name: str, img: QImage):
        icon_dir = get_settings_dir() / ICON_DIR
        if not icon_dir.exists():
            icon_dir.mkdir()
        p = Path(get_settings_dir() / ICON_DIR / exe_name).with_suffix('.png')

        try:
            writer = QImageWriter()
            writer.setFormat(b'png')
            writer.setFileName(str(WindowsPath(p)))
            writer.write(img)
        except Exception as e:
            logging.error('Could not write icon file: %s', e)

        logging.info('Icon for %s written to disk: %s', exe_name, p)

    @staticmethod
    def _read_image(file: Path) -> Optional[QImage]:
        try:
            with open(file.as_posix(), 'rb') as f:
                img_content = f.read()

            img = QImage.fromData(img_content)
            return img
        except Exception as e:
            logging.error('Error reading image file: %s', e)

    def _get_icon_files_from_disk(self):
        for file in Path(get_settings_dir() / ICON_DIR).glob('*.png'):
            exe_name = file.with_suffix('.exe').name
            img = self._read_image(file)
            if img:
                logging.debug('Read image icon from disk: %s %s', exe_name, img.size())
                self.icon_files[exe_name] = img

    def _get_existing_icon(self, exe_path: Path) -> bool:
        if exe_path.name not in self.icon_files:
            return False

        img = self.icon_files.get(exe_path.name)
        q_pixmap = QPixmap.fromImage(img)
        self.pixmap_signal.emit(exe_path.name, q_pixmap)
        return True

    def request_exe(self, exe_path: Path):
        if exe_path in self.orders:
            return

        logging.debug('Exe icon requested thru receiver thread: %s', exe_path)
        self.orders.add(exe_path)
