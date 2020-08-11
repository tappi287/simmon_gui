from qtpy.QtCore import QObject, QTimer

from modules.gui.guiutil import AskToContinue
from modules.watcher_install import find_installed_watcher_task, start_watcher_task


class WatcherController(QObject):
    update_timer = QTimer()
    update_timer.setInterval(100)

    def __init__(self, ui, status_label, update_button, start_button, stop_button):
        """ Continuously update the background watcher status.

        :param SimmonUi ui:
        :param QLabel status_label:
        :param QPushButton update_button:
        """
        super(WatcherController, self).__init__(ui)
        self.ui = ui
        self.app = ui.app
        self.status_label = status_label

        self.update_button = update_button
        self.start_button = start_button
        self.stop_button = stop_button

        self.update_button.released.connect(self.restart_watcher)
        self.stop_button.released.connect(self.stop_watcher)
        self.start_button.released.connect(self.start_watcher)

        self.update_timer.timeout.connect(self.update_status)

        self.update_timer.start()

    def restart_watcher(self):
        self.update_timer.start()
        self.app.set_shared_memory_state(b'READ')

    def start_watcher(self):
        if find_installed_watcher_task():
            watcher_started = start_watcher_task()
        else:
            msg_box = AskToContinue(self.ui)

            if not msg_box.ask('Watchman Task Installation',
                               'Watchman task is not installed. Do you want to install it now?',
                               'Install', 'Cancel'):
                # User wants to abort installation
                return

            self.ui.options_menu.install_action.trigger()
            watcher_started = True

        if watcher_started:
            self.start_button.setEnabled(False)

    def stop_watcher(self):
        self.app.set_shared_memory_state(b'EXIT')

    def update_status(self):
        share = self.app.read_shared_memory()
        self.update_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(False)

        if share == b'RUN_':
            self.status_label.setText('Watchman <span style="color: green;">active</span>')
            self.update_button.setEnabled(True)
            self.stop_button.setEnabled(True)
        elif share == b'READ':
            self.status_label.setText('Waiting for Watchman to restart')
            self.update_button.setEnabled(True)
            self.stop_button.setEnabled(True)
        elif share == b'EXIT':
            self.status_label.setText('Watchman is shutting down')
        elif share is None:
            self.status_label.setText('Watchman <i>not</i> running')
            self.start_button.setEnabled(True)
        else:
            self.status_label.setText('Status could <span style="color: red;">not</span> be detected')
            self.start_button.setEnabled(True)
