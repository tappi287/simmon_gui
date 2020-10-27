import logging
import os
from pathlib import Path
from threading import Event

from qtpy.QtCore import QTimer, Qt, Signal
from qtpy.QtGui import QIcon, QPixmap, QCloseEvent
from qtpy.QtWidgets import QAction, QLabel, QMainWindow, QPushButton, QTabWidget, QWidget
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Session

from shared_modules.models import Profile
from .addprofilemenu import AddProfileMenu
from .expandable_widget import ExpandableWidget
from .file_dialog import FileDialog
from .get_icon import IconReceiverThread
from .guiutil import GenericMsgBox, remove_from_db
from .log_view import LogViewerWindow
from .optionsmenu import OptionsMenu
from .profile import ProfileWidget
from .quick_start import QuickStartTab
from .watch_controller import WatcherController
from ..import_export import ProfileImportExport
from ..path_util import path_exists
from ..ui_loader import SetupWidget


class SimmonUi(QMainWindow):
    debounce_timer = QTimer()
    debounce_timer.setInterval(300)
    debounce_timer.setSingleShot(True)

    watcher_update_trigger = QTimer()
    watcher_update_trigger.setInterval(8000)
    watcher_update_trigger.setSingleShot(True)

    icons_updated = Signal(str)
    request_exe_icon = Signal(Path)
    start_shutdown = Signal()

    exe_icons = dict()

    def __init__(self, app):
        """

        :param modules.app.SimmonApp app:
        """
        super(SimmonUi, self).__init__()
        SetupWidget.from_ui_file(self, 'main.ui')
        self.app = app
        self.session = Session(app.db_engine)

        # -- Add LogViewer --
        self.actionLog: QAction
        self.actionLog.triggered.connect(self.view_log)
        self.actionAppLog: QAction
        self.actionAppLog.triggered.connect(self.view_app_log)

        # -- Import Profile --
        self.actionImport: QAction
        self.actionImport.triggered.connect(self.import_profile)

        # -- Setup ProfileWidget --
        self.profileTabWidget: QTabWidget
        self.profileTabWidget.tabCloseRequested.connect(self.close_profile_tab)
        self.add_profile_btn = QPushButton(QIcon(':main/add-24px.svg'), '', self)
        self.add_profile_btn.setStatusTip('Add a new profile')
        # self.add_profile_btn.released.connect(self.add_new_profile)
        self.add_profile_menu = AddProfileMenu(self, self.add_profile_btn, self.add_new_profile)
        self.profileTabWidget.setCornerWidget(self.add_profile_btn, Qt.TopLeftCorner)

        # -- Setup Quick Start Widget --
        self.quick_start = QuickStartTab(self)
        self.profileTabWidget.addTab(self.quick_start, 'Quick Start')

        # -- Setup Watchmen Widget --
        self.watcherExpandBtn: QPushButton
        self.watcher_expand_widget = ExpandableWidget(self.watcherWidget, self.watcherExpandBtn)

        # -- Setup Watchmen Controller --
        self.watcherWidget: QWidget
        self.watcherStatusLabel: QLabel
        self.watcherStatusText: QLabel
        self.watcherStatusText.setStatusTip('Displays the status of the background service.')
        self.watcherUpdateBtn: QPushButton
        self.watcherUpdateBtn.setStatusTip('Request the background service to restart and re-read the database')
        self.watcherStartBtn: QPushButton
        self.watcherStartBtn.setStatusTip('Start the background Watchman service that executes your profiles')
        self.watcherStopBtn: QPushButton
        self.watcherStopBtn.setStatusTip('Exit the background Watchman service')

        self.watch_controller = WatcherController(self, self.watcherStatusText, self.watcherUpdateBtn,
                                                  self.watcherStartBtn, self.watcherStopBtn)

        # -- Get icon thread --
        self.icon_exit = Event()
        self.get_icons_thread = IconReceiverThread(self, self.icon_exit)
        self.get_icons_thread.pixmap_signal.connect(self.update_exe_icon)
        self.request_exe_icon.connect(self.get_icons_thread.request_exe)
        QTimer.singleShot(1500, self.get_icons_thread.start)

        self.options_menu = OptionsMenu(self)
        self.menuBar().addMenu(self.options_menu)

        self.watcher_update_trigger.timeout.connect(self.update_watcher)

        self.setWindowTitle(f'{self.app.applicationDisplayName()}')
        self.create_widgets()

        self.install_event()
        self._ready_to_quit = False
        self.start_shutdown.connect(self._shutdown)

    def closeEvent(self, event: QCloseEvent):
        self.icon_exit.set()

        if not self._ready_to_quit:
            self.start_shutdown.emit()
            event.ignore()
            return False

        event.accept()
        return True

    def _shutdown(self):
        self.get_icons_thread.join(timeout=10)
        self._ready_to_quit = True
        QTimer.singleShot(100, self.close)

    def start_get_executable_icon(self, exe_path: Path):
        if not exe_path.is_file():
            return

        self.setStatusTip(f'Loading executable icon for {exe_path.name} ...')
        logging.info('UI Requesting Icon from executable %s', exe_path.name)
        self.request_exe_icon.emit(exe_path)

    def update_exe_icon(self, exe_name: str, pixmap: QPixmap):
        logging.debug('Updating UI Exe Icons: %s', exe_name)
        self.setStatusTip(f'Loaded executable icon for {exe_name}')
        self.exe_icons[exe_name] = pixmap
        self.icons_updated.emit(exe_name)

    def install_event(self):
        """ Trigger Watcher updates from database commits inside the GUI """
        @listens_for(self.app.db_engine, 'commit')
        def listen(*args, **kwargs):
            self.watcher_update_trigger.start()

        logging.debug('Installed SQLAlchemy Event listener for commits.')

    def update_watcher(self):
        """ Tell Watcher to re-read database """
        logging.debug('Watcher re-read triggered. Database updates detected.')
        self.watch_controller.restart_watcher()

    def ready(self):
        """ Check if Ui was updated within last debounce interval or
            start new debounce interval.

            Stop button smashing.
        """
        if self.debounce_timer.isActive():
            return False
        self.debounce_timer.start()
        return True

    def refresh_profiles(self):
        idx = self.profileTabWidget.count()

        while idx:
            idx -= 1

            if self.profileTabWidget.widget(idx) != self.quick_start:
                self.profileTabWidget.removeTab(idx)

        self.create_widgets()

    def close_profile_tab(self, index: int):
        widget: ProfileWidget = self.profileTabWidget.widget(index)
        if widget.ask_on_close():
            self.profileTabWidget.removeTab(index)
            widget.deleteLater()

        if self.profileTabWidget.count() == 0:
            # -- Create default profile --
            self.add_new_profile()

    def add_new_profile(self) -> None:
        """ Add db entry and widget """
        if self.ready():
            self.add_profile_widget(self.add_db_profile_entry())

    def add_db_profile_entry(self) -> Profile:
        profile = Profile(name=f'Profile_{self.profileTabWidget.count():02d}')
        self.session.add(profile)
        self.session.commit()
        return profile

    def add_profile_widget(self, profile: Profile):
        profile_widget = ProfileWidget(self, profile)
        self.profileTabWidget.addTab(profile_widget, profile_widget.windowTitle())

    def remove_db_profile_entry(self, profile_id: int) -> bool:
        """
        tasks = self.session.query(Task).filter_by(profile_id=profile_id)
        conditions = list()

        # - Remove associated Tasks
        for task in tasks:
            task_con = self.session.query(Condition).filter_by(task_id=task.id)
            if task_con:
                conditions += task_con
            remove_from_db(self.session, Task, task.id)

        # - Remove associated Conditions
        for condition in conditions:
            remove_from_db(self.session, Condition, condition.id)
        """
        return remove_from_db(self.session, Profile, profile_id)

    def create_widgets(self):
        for profile in self.session.query(Profile).all():
            logging.info('Creating widget: %s', profile.name)
            profile_widget = ProfileWidget(self, profile)
            self.profileTabWidget.addTab(profile_widget, profile_widget.windowTitle())

        if self.profileTabWidget.count() == 0:
            # -- Create default profile --
            self.add_new_profile()

    def view_log(self):
        log_view = LogViewerWindow(self)
        log_view.show()

    def view_app_log(self):
        log_view = LogViewerWindow(self, display_watcher_log=False)
        log_view.show()

    def import_profile(self):
        file = FileDialog.open_existing_file(self, directory=Path(os.path.expanduser('~')))
        if not file:
            return

        m = GenericMsgBox(self, 'Error', f'Could not open file: {file}')

        if path_exists(file):
            ProfileImportExport.auto_detected_msg_ls = list()

            if not ProfileImportExport.import_profile(Path(file), use_known_apps=True):
                m.setText('Error while importing Profile!')
                m.exec_()
                return

            if ProfileImportExport.auto_detected_msg_ls:
                m.setWindowTitle('Auto detection')
                m.setText(f'SimMon automatically detected local install locations:<br /><br />'
                          f'{"<br />".join(set(ProfileImportExport.auto_detected_msg_ls))}<br /><br />'
                          f'Conditions and Process entries have been updated...')
                m.exec_()
        else:
            m.exec_()
            return

        self.refresh_profiles()
