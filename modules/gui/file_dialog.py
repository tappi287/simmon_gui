import logging
from pathlib import Path
from typing import Union
from modules.path_util import path_exists

from qtpy import QtWidgets


class FileDialog:
    """
        Shorthand class to create file dialogs. Dialog will block.
            file_key: see class attribute file_types
    """
    file_types = dict(
        json=dict(title='Select JSON *.json', filter='Json Files (*.json)'),
        dir=dict(title='Choose directory ...', filter=None)
        )
    current_path = None

    @classmethod
    def open(cls,
             parent=None, directory: Union[Path, str] = None, file_key: str = 'xml'
             ) -> Union[str, None]:
        return cls.open_existing_file(parent, directory, file_key)

    @classmethod
    def save(cls, parent, directory: Path, file_key: str = 'xml') -> tuple:
        directory = cls._get_current_dir(directory)
        return cls.__create_save_dialog(parent, cls.file_types[file_key]['title'],
                                        directory, cls.file_types[file_key]['filter'])

    @classmethod
    def _get_current_dir(cls, directory: Path):
        if cls.current_path is not None and cls.current_path.exists():
            directory = cls.current_path
        if directory.exists():
            cls.current_path = directory
        else:
            directory = Path('.')
        return directory

    # -------------------------------
    # ------- Dialog creation -------
    @staticmethod
    def __create_file_dialog(parent, title: str, directory: Path, file_filter: str) -> tuple:
        # Create and configure File Dialog
        dlg = QtWidgets.QFileDialog()
        dlg.setFileMode(QtWidgets.QFileDialog.ExistingFile)

        # This will block until the user has selected a file or canceled
        return dlg.getOpenFileName(parent, title, directory.as_posix(), file_filter)

    @staticmethod
    def __create_save_dialog(parent, title: str, directory: Path, file_filter: str) -> tuple:
        dlg = QtWidgets.QFileDialog()
        return dlg.getSaveFileName(parent, title, directory.as_posix(), file_filter)

    @classmethod
    def open_existing_file(cls, parent=None, directory: Path = None,
                           file_key: str = 'json') -> Union[str, None]:
        # Update path
        directory = cls._get_current_dir(Path(directory or Path('.')))

        # Update filter and title depending on file type
        if file_key not in cls.file_types.keys():
            file_key = 'xml'

        title = cls.file_types[file_key]['title']
        file_filter = cls.file_types[file_key]['filter']

        file, file_ext = cls.__create_file_dialog(parent, title, directory, file_filter)

        if file and path_exists(file):
            if Path(file).suffix != f'.{file_key}':
                logging.warning(f'User supposed to open: %s but opened: %s - returning None',
                                f'.{file_key}', Path(file).suffix)
                return

            cls.current_path = Path(file).parent

        return file
