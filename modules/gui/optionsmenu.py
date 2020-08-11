import logging
from pathlib import Path, WindowsPath
from subprocess import Popen
from typing import Optional

from qtpy.QtWidgets import QAction, QMenu

from shared_modules.globals import APP_NAME, FROZEN, WATCHER_EXE_NAME, WIN_AUTOSTART_DIR, \
    get_current_modules_dir
from modules.gui.guiutil import GenericMsgBox
from modules.watcher_install import install_watcher_task, uninstall_watcher_task, find_installed_watcher_task, \
    start_watcher_task


class OptionsMenu(QMenu):
    watcher_exe = Path(get_current_modules_dir()) / WATCHER_EXE_NAME

    def __init__(self, ui):
        """

        :param SimmonUi ui:
        """
        super(OptionsMenu, self).__init__(ui)
        self.setTitle('Options')
        self.ui = ui

        self.install_action = QAction('Install Watchman as Windows logon task', self)
        self.install_action.setCheckable(True)
        self.install_action.setChecked(True if find_installed_watcher_task() else False)
        self.install_action.setStatusTip('Creates or removes a task that will run the Watchman at Windows user logon')
        self.install_action.toggled.connect(self.toggle_watcher_installation)

        self.addAction(self.install_action)

    def toggle_watcher_installation(self, checked):
        if checked:
            self.install_watcher_task()
        else:
            uninstall_watcher_task()

    def uncheck_install_action(self):
        """ Uncheck action without emitting a toggle signal """
        self.install_action.blockSignals(True)
        self.install_action.setChecked(False)
        self.install_action.blockSignals(False)

    def install_watcher_task(self):
        if not FROZEN:
            logging.error('Can not install Watcher Windows Task from IDE environment.')
            self.uncheck_install_action()
            m = GenericMsgBox(self.ui, 'Error', 'Can not install Watcher Windows Task from IDE environment.')
            m.exec_()
            return

        result = install_watcher_task()
        logging.debug('Install Task result: %s', result)

        if result is None or result != 0:
            self.uncheck_install_action()
            m = GenericMsgBox(self.ui, 'Error', f'Could not install Watchman Task: {result}')
            m.exec_()
            return

        start_watcher_task()

    def install_watcher_autostart(self):
        lnk_path = Path(WIN_AUTOSTART_DIR) / f'{APP_NAME}_watcher.lnk'
        create_link = f'$link = (New-Object -COM WScript.Shell).CreateShortcut("{str(WindowsPath(lnk_path))}")'
        if FROZEN:
            set_link = f'$link.targetpath = "{str(WindowsPath(self.watcher_exe))}"'
        else:
            dist_dir = Path(get_current_modules_dir()) / 'dist' / APP_NAME / WATCHER_EXE_NAME
            set_link = f'$link.targetpath = "{str(WindowsPath(dist_dir))}"'

        cmd = f"{create_link};{set_link};$link.save()"
        logging.info('Autostart install cmd:\n%s', cmd)

        p = Popen(['powershell', cmd])
        result = p.communicate()
        logging.info('Watcher autostart install result: %s', result)

    def uninstall_watcher_autostart(self):
        try:
            file = self.find_autostart_entry()
            if file is None:
                logging.info('Autostart entry not found.')
                return
            file.unlink()
            logging.info('Removed watcher autostart entry: %s', file.name)
        except Exception as e:
            logging.error(e)

    @staticmethod
    def find_autostart_entry() -> Optional[Path]:
        for file in Path(WIN_AUTOSTART_DIR).glob('*.lnk'):
            if file.name.startswith(APP_NAME):
                return file