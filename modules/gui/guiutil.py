import enum
import logging
from pathlib import Path, WindowsPath
from typing import Tuple

from qtpy.QtGui import QColor, QIcon, QPalette, QPixmap
from qtpy.QtWidgets import QMessageBox, QWidget
from qtpy.QtCore import Property, QAbstractAnimation, QEasingCurve, QObject, QPropertyAnimation, Signal
from sqlalchemy.orm import Session

from shared_modules.globals import get_current_modules_dir, UI_PATH
from shared_modules.models import Base
from ..path_util import SetDirectoryPath


def update_db_entry(session: Session, base_class: Base, object_id: int, name: str, value: object) -> bool:
    o = session.query(base_class).filter_by(id=object_id).first()
    try:
        setattr(o, name, value)
        session.commit()
    except Exception as e:
        logging.error('Error updating %s db entry Id %s: %s', base_class.__name__, object_id, e)
        return False
    logging.debug('Updated %s db entry Id %s: %s: %s', base_class.__name__, object_id, name, value)
    return True


def remove_from_db(session: Session, base_class: Base, object_id: int) -> bool:
    """ Permanently remove this object database instance """
    o = session.query(base_class).filter_by(id=object_id).first()

    if o:
        try:
            session.delete(o)
            session.commit()
            logging.debug('Removed %s Id %s from database.', base_class.__name__, object_id)
            return True
        except Exception as e:
            logging.error('Could not remove %s Id %s from database. Error: %s',
                          base_class.__name__, object_id, e)
            return False
    else:
        logging.error('Could not remove %s Id %s from database. It does not exists in the database.',
                      base_class.__name__, object_id)
        return False


class ExecutableFields(QObject):
    executable_changed = Signal()
    executable_invalid = Signal()
    executable_valid = Signal()

    def __init__(self, parent, db_base_class: Base, db_session: Session, db_id: int,
                 path_line_edit, path_btn, executable, path):
        super(ExecutableFields, self).__init__(parent)

        self.db_base_class = db_base_class
        self.db_session = db_session
        self.db_id = db_id
        self.parent = parent

        self.bgr_animation = BgrAnimation(path_line_edit)

        self.executable = executable
        self.path = path

        self.path_util = SetDirectoryPath(parent, mode='file',
                                          line_edit=path_line_edit, tool_button=path_btn,
                                          reject_invalid_path_edits=False)
        self.path_util.path_changed.connect(self.set_executable)
        self.path_util.set_path(Path(path) / executable)

    def trigger_update(self):
        """ Used in delayed setup to render elements with valid/invalid executable paths """
        self.path_util.set_path(Path(self.path) / self.executable)

    def set_executable(self, exe_path: Path):
        exe_valid = True

        # - Highlight Path does not exists
        if not exe_path.is_file():
            logging.debug('Activating pulsate')
            self.bgr_animation.active_pulsate()
            exe_valid = False
        else:
            self.bgr_animation.blink()

        # - Check that path does not point to a directory
        if exe_path.suffix == '':
            self.executable_invalid.emit()
            return

        if not exe_valid:
            self.executable_invalid.emit()
        else:
            self.executable_valid.emit()

        self.executable = exe_path.name
        self.path = str(WindowsPath(exe_path.parent))
        update_db_entry(self.db_session, self.db_base_class, self.db_id,
                        'executable', self.executable)
        update_db_entry(self.db_session, self.db_base_class, self.db_id,
                        'path', self.path)

        self.executable_changed.emit()


class GenericMsgBox(QMessageBox):
    def __init__(self, parent, title: str = 'Message Box', text: str = 'Message Box.'):
        super(GenericMsgBox, self).__init__()
        self.parent = parent

        icn = Path(get_current_modules_dir()) / UI_PATH / 'sm_icon.png'
        self.setWindowIcon(QIcon(QPixmap(icn.as_posix())))
        self.setWindowTitle(title)
        self.setIcon(QMessageBox.Information)
        self.setText(text)


class AskToContinue(GenericMsgBox):
    title = 'Continue?'

    txt = 'Do you really want to perform this action?'

    continue_txt = 'Continue'
    abort_txt = 'Cancel'

    def __init__(self, parent):
        super(AskToContinue, self).__init__(parent, self.title, self.txt)
        self.setIcon(QMessageBox.Information)
        self.setStandardButtons(QMessageBox.Ok | QMessageBox.Abort)
        self.setDefaultButton(QMessageBox.Abort)

    def ask(self, title: str = '', txt: str = '', ok_btn_txt: str = '', abort_btn_txt: str = ''):
        if title:
            self.setWindowTitle(title)
        if txt:
            self.setText(txt)

        ok_btn_txt = ok_btn_txt or self.continue_txt
        abort_btn_txt = abort_btn_txt or self.abort_txt

        self.button(QMessageBox.Ok).setText(ok_btn_txt)
        self.button(QMessageBox.Abort).setText(abort_btn_txt)

        if self.exec_() == QMessageBox.Ok:
            return True
        return False


class AskToContinueCritical(AskToContinue):
    def __init__(self, parent):
        super(AskToContinueCritical, self).__init__(parent)
        self.setIcon(QMessageBox.Critical)


class BgrAnimation(QObject):
    def __init__(self, widget: QWidget, bg_color: Tuple[int, int, int, int] = None, additional_stylesheet: str=''):
        """ Animate provided Widget background stylesheet color

        :param widget:
        :param bg_color:
        """
        super(BgrAnimation, self).__init__(widget)
        self.widget = widget
        self.color = QColor()

        self.bg_color = self.widget.palette().color(QPalette.Background)
        self.additional_stylesheet = additional_stylesheet
        if bg_color:
            self.bg_color = QColor(*bg_color)

        self.color_anim = QPropertyAnimation(self, b'backColor')
        self.color_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._setup_blink()

        self.pulsate_anim = QPropertyAnimation(self, b'backColor')
        self.pulsate_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._setup_pulsate()

        self.fade_anim = QPropertyAnimation(self, b'backColor')
        self.fade_anim.setEasingCurve(QEasingCurve.InCubic)

    def fade(self, start_color: tuple, end_color: tuple, duration:int):
        self.fade_anim.setStartValue(QColor(*start_color))
        self.fade_anim.setEndValue(QColor(*end_color))
        self.fade_anim.setDuration(duration)

        self.fade_anim.start(QAbstractAnimation.KeepWhenStopped)

    def _setup_blink(self, anim_color: tuple=(26, 118, 255, 255)):
        start_color = self.bg_color
        anim_color = QColor(*anim_color)

        self.color_anim.setStartValue(start_color)
        self.color_anim.setKeyValueAt(0.5, anim_color)
        self.color_anim.setEndValue(start_color)

        self.color_anim.setDuration(700)

    def blink(self, num: int=1):
        self.pulsate_anim.stop()
        self.color_anim.setLoopCount(num)
        self.color_anim.start()

    def _setup_pulsate(self, anim_color: tuple=(255, 120, 50, 255)):
        start_color = self.bg_color
        anim_color = QColor(*anim_color)

        self.pulsate_anim.setStartValue(start_color)
        self.pulsate_anim.setKeyValueAt(0.5, anim_color)
        self.pulsate_anim.setEndValue(start_color)

        self.pulsate_anim.setDuration(800)

    def active_pulsate(self, num: int=-1):
        self.pulsate_anim.setLoopCount(num)
        self.pulsate_anim.start()

    def _get_back_color(self):
        return self.color

    def _set_back_color(self, color):
        self.color = color
        qss_color = f'rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})'
        try:
            self.widget.setStyleSheet(f'background-color: {qss_color};{self.additional_stylesheet}')
        except AttributeError as e:
            logging.debug('Error setting widget background color: %s', e)

    backColor = Property(QColor, _get_back_color, _set_back_color)


class SizeUnit(enum.Enum):
    BYTES = 1
    KB = 2
    MB = 3
    GB = 4


def convert_unit(size_in_bytes, unit):
    """ Convert the size from bytes to other units like KB, MB or GB"""
    size_in_bytes = int(size_in_bytes)
    if unit == SizeUnit.KB:
        return size_in_bytes / 1024
    elif unit == SizeUnit.MB:
        return size_in_bytes / (1024 * 1024)
    elif unit == SizeUnit.GB:
        return size_in_bytes / (1024 * 1024 * 1024)
    else:
        return size_in_bytes