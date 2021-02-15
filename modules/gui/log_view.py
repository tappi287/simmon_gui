import logging
from pathlib import Path

from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QShowEvent
from qtpy.QtWidgets import QDialog, QPushButton, QTextBrowser

from shared_modules.globals import WATCHER_NAME, APP_NAME, get_log_dir
from modules.ui_loader import SetupWidget


class LogViewerWindow(QDialog):
    def __init__(self, ui, display_watcher_log: bool = True):
        """

        :param modules.gui.ui.SimmonUi ui:
        """
        super(LogViewerWindow, self).__init__(ui)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.ui = ui
        self.display_watcher_log = display_watcher_log

        SetupWidget.from_ui_file(self, 'log_viewer.ui')
        self.label.setText(f'Displays latest 100 log entries for '
                           f'{"background watcher" if self.display_watcher_log else "gui application"}.')
        self.textBrowser: QTextBrowser
        self.update_text_browser()

        self.refreshBtn: QPushButton
        self.refreshBtn.released.connect(self.refresh)

        self.auto_refresh = QTimer(self)
        self.auto_refresh.setInterval(60000)
        self.auto_refresh.timeout.connect(self.refresh)
        self.auto_refresh.start()

    def refresh(self):
        if self.ui.ready():
            self.update_text_browser()

    def update_text_browser(self):
        if self.display_watcher_log:
            log_file = Path(get_log_dir()) / f'{WATCHER_NAME}.log'
        else:
            log_file = Path(get_log_dir()) / f'{APP_NAME}.log'

        if not log_file.exists():
            self.textBrowser.setText('Log file not found.')
            return

        log_lines = list()
        with open(log_file, 'r') as f:
            log_lines = f.readlines()

        # Shorten log document
        if len(log_lines):
            log_lines = log_lines[min(len(log_lines)-1, len(log_lines)-100):]

        self.textBrowser.setText(''.join(reversed(log_lines)))

        # url = QUrl.fromLocalFile(log_file.as_posix())
        # self.textBrowser.setSource(url)

    def showEvent(self, show_event: QShowEvent):
        """ move Dialog to parent window center """
        dlg_center = self.rect().center()
        self.auto_refresh.start()
        p = self.ui.window().mapToGlobal(self.ui.window().rect().center())
        center = p - dlg_center
        self.move(center)
