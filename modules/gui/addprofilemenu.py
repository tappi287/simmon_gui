import json
import logging
from pathlib import Path
from typing import Optional

from qtpy.QtWidgets import QAction, QMenu, QPushButton

from modules.gui.guiutil import GenericMsgBox
from modules.import_export import ProfileImportExport
from modules.path_util import path_exists
from shared_modules.globals import get_default_profiles_dir


class AddProfileMenu(QMenu):
    def __init__(self, ui, button: QPushButton, add_profile_callback):
        """

        :param modules.gui.ui.SimmonUi ui:
        :param button:
        """
        super(AddProfileMenu, self).__init__(ui)
        self.ui = ui
        self.button = button
        self.button.setMenu(self)
        self.add_profile_callback = add_profile_callback

        add_profile = QAction('<Add new Profile>', self)
        add_profile.triggered.connect(add_profile_callback)
        self.addAction(add_profile)

        self.setup_default_profiles()

    def _add_profile_entry(self, profile: dict, file: Path):
        a = QAction(profile.get('name'), self)
        a.profile_path = file
        a.triggered.connect(self.import_default_profile)
        self.addAction(a)

    def import_default_profile(self):
        action = self.sender()
        m = GenericMsgBox(self, 'Error', 'Error while importing Profile!')

        if not ProfileImportExport.import_profile(action.profile_path, use_known_apps=True):
            m.exec_()
            return

        if ProfileImportExport.auto_detected_msg_ls:
            m.setWindowTitle('Auto detection')
            m.setText(f'SimMon automatically detected local install locations:<br /><br />'
                      f'{"<br />".join(set(ProfileImportExport.auto_detected_msg_ls))}<br /><br />'
                      f'Conditions and Process entries have been updated...')
            m.exec_()

        self.ui.refresh_profiles()

    @staticmethod
    def _read_profile(file: Path) -> Optional[dict]:
        try:
            with open(file.as_posix(), 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error('Error reading default profile file %s: %s', file.name, e)

    def setup_default_profiles(self):
        profile_dir = Path(get_default_profiles_dir())
        known_apps_file = profile_dir / 'known_apps.json'

        for file in profile_dir.glob('*.json'):
            if file == known_apps_file:
                continue
            profile = self._read_profile(file)

            if profile:
                self._add_profile_entry(profile, file)

