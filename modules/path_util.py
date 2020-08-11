"""
gui_set_path module provides a file dialog for selecting paths or a line edit to paste and display the chosen path

Copyright (C) 2017 Stefan Tapper, All rights reserved.

    This file is part of RenderKnecht Strink Kerker.

    RenderKnecht Strink Kerker is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    RenderKnecht Strink Kerker is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with RenderKnecht Strink Kerker.  If not, see <http://www.gnu.org/licenses/>.

"""
import logging
import os.path
from pathlib import Path
from typing import Union

from qtpy.QtCore import QObject, QRegExp, Qt, Signal
from qtpy.QtGui import QRegExpValidator
from qtpy.QtWidgets import QFileDialog, QLineEdit, QToolButton


def path_exists(p: Union[Path, str]) -> bool:
    """ Accessing pathlib.Path.exists can throw all kinds of wierd errors
        try to catch exceptions here,
    """
    try:
        p = Path(p)
        if not p.exists():
            return False
    except OSError as e:
        logging.error('Can not access path: %s', e)
        return False

    return True


class SetDirectoryPath(QObject):
    path_changed = Signal(Path)
    invalid_path_entered = Signal()

    def __init__(self,
                 parent,
                 mode='dir',
                 line_edit: QLineEdit=None,
                 tool_button: QToolButton=None,
                 dialog_args=(),
                 reject_invalid_path_edits=False):
        super(SetDirectoryPath, self).__init__(parent)
        self.line_edit, self.tool_button = line_edit, tool_button
        self.mode = mode

        self.path = None

        self.parent = parent

        if self.tool_button:
            self.dialog_args = dialog_args
            self.tool_button.pressed.connect(self.btn_open_dialog)

        self.reject_invalid_path_edits = reject_invalid_path_edits
        if self.line_edit:
            regex = QRegExp(r'[^<>?"|*´`ß]*')
            regex.setCaseSensitivity(Qt.CaseInsensitive)
            self.line_edit.setValidator(QRegExpValidator(regex))

            self.line_edit.editingFinished.connect(self.path_text_changed)

    def btn_open_dialog(self):
        current_path = Path('.')

        if self.line_edit:
            line_edit_path = Path(self.line_edit.text())

            if path_exists(line_edit_path):
                current_path = line_edit_path

        if self.path:
            current_path = self.path

        self.get_directory_file_dialog(current_path, *self.dialog_args)

    def get_directory_file_dialog(self, current_path, title='Choose directory', file_filter='(*.*)'):
        if not path_exists(current_path) or current_path == '':
            current_path = Path('.')
        else:
            current_path = Path(current_path)

        if self.mode == 'dir':
            current_path = QFileDialog.getExistingDirectory(
                self.parent, caption=title, dir=current_path.as_posix()
            )
            if not current_path:
                return
        else:
            current_path, file_type = QFileDialog.getOpenFileName(
                self.parent, caption=title, dir=current_path.as_posix(), filter=file_filter
            )
            if not file_type:
                return

        if self.mode == 'file2dir':
            if Path(current_path).is_file():
                current_path = Path(current_path).parent

        current_path = Path(current_path)

        self.set_path(current_path)

        return current_path

    def set_path(self, current_path: Union[Path, str]):
        current_path = Path(current_path)
        if not path_exists(current_path) and self.reject_invalid_path_edits:
            return

        # Update line edit
        self.set_path_text(current_path)

        # Emit change
        self.path_changed.emit(current_path)

        # Set own path var
        self.path = current_path

    def set_path_text(self, current_path):
        if not self.line_edit:
            return

        self.line_edit.setText(str(current_path))

    def path_text_changed(self):
        """ line edit text changed """
        text_path = Path(self.line_edit.text())

        if text_path.exists():
            self.set_path(text_path)
        else:
            # Pasted or typed Path does not exist
            if self.reject_invalid_path_edits:
                self.line_edit.clear()
                self.line_edit.setPlaceholderText('Enter valid file path')
                return
            self.set_path(text_path)
