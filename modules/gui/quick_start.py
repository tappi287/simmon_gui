from pathlib import Path, WindowsPath

from qtpy.QtCore import QUrl
from qtpy.QtWidgets import QPushButton, QTableWidget, QTableWidgetItem, QTextBrowser, QWidget

from modules.gui.guiutil import SizeUnit, convert_unit
from modules.steam_utils import STEAM_LIBRARY_FOLDERS, SteamApps
from modules.ui_loader import SetupWidget
from shared_modules.globals import get_current_modules_dir


class QuickStartTab(QWidget):
    def __init__(self, ui):
        super(QuickStartTab, self).__init__(ui)
        self.ui = ui

        SetupWidget.from_ui_file(self, 'quick_widget.ui')

        # -- Setup Quick Start Widget --
        self.quickExpandBtn: QPushButton
        self.quickTextBrowser: QTextBrowser
        url = QUrl.fromLocalFile(Path(Path(get_current_modules_dir()) / 'ui' / 'quick_start.html').as_posix())
        self.quickTextBrowser.setSource(url)

        self.steamExpandBtn: QPushButton
        self.steam_first_expand = True
        self.steamExpandBtn.pressed.connect(self.setup_steam_table)

    def setup_steam_table(self):
        if not self.steam_first_expand:
            return
        self.steam_first_expand = False

        # -- Short cuts --
        s = SteamApps()
        t: QTableWidget = self.steamTable
        q: QTableWidgetItem = QTableWidgetItem

        # -- Update Table Data --
        t.setColumnCount(4)
        t.setHorizontalHeaderLabels(
            ('App ID', 'Name', 'Path', 'Size')
            )
        t.setColumnWidth(0, 80)
        t.setColumnWidth(1, 280)
        t.setColumnWidth(2, 400)
        t.setColumnWidth(3, 80)

        # -- Known Apps
        for row, (app_id, manifest) in enumerate(s.known_apps.items(), start=t.rowCount()):
            if app_id in s.steam_apps:
                s.steam_apps.pop(app_id)

            t.setRowCount(row + 1)
            t.setItem(row, 0, q(app_id))
            t.setItem(row, 1, q(manifest.get('name')))

            path = Path(manifest.get('path')) / manifest.get('executable')
            t.setItem(row, 2, q(str(WindowsPath(path))))

            size_bytes = manifest.get('SizeOnDisk', 0)
            size = f"{convert_unit(size_bytes, SizeUnit.GB):.02f} GB"
            t.setItem(row, 3, q(f"{'N/A' if not size_bytes else size}"))

        # -- Steam Apps
        s.steam_apps.pop(STEAM_LIBRARY_FOLDERS)

        for row, (app_id, manifest) in enumerate(s.steam_apps.items(), start=t.rowCount()):
            t.setRowCount(row + 1)
            t.setItem(row, 0, q(app_id or 'Unknown'))
            t.setItem(row, 1, q(manifest.get('name', '')))
            t.setItem(row, 2, q(str(WindowsPath(manifest.get('path', '')))))
            t.setItem(row, 3, q(f"{convert_unit(manifest.get('SizeOnDisk', 0), SizeUnit.GB):.0f} GB"))
