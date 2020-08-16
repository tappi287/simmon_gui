import logging
from pathlib import Path, WindowsPath

from qtpy.QtCore import QSize
from qtpy.QtWidgets import QComboBox, QLabel, QLineEdit, QPushButton, QToolButton, QWidget

from shared_modules.models import NOTIFICATION_TYPES, Process
from shared_modules.utils import get_file_properties
from .guiutil import AskToContinue, ExecutableFields, update_db_entry
from ..ui_loader import SetupWidget


class ProcessWidget(QWidget):
    def __init__(self, profile_widget, process: Process):
        """

        :param modules.gui.profile.ProfileWidget profile_widget:
        :param process:
        """
        super(ProcessWidget, self).__init__(profile_widget)
        self.profile_widget = profile_widget

        SetupWidget.from_ui_file(self, 'process_widget.ui')

        self.processName: QLabel
        self.processName.setText(process.name)
        self.processIconLabel: QLabel
        self.processIconLabel.setFixedSize(QSize(48, 48))

        self.processNotificationType: QComboBox
        self.processNotificationType.setStatusTip('Creation - the process was started, '
                                                  'Deletion - the process has ended, '
                                                  'Modification/Operation - the process is active: '
                                                  'CPU heavy do not use for now')
        self.processNotificationType.addItems(NOTIFICATION_TYPES)
        for i in range(0, self.processNotificationType.count()):
            if self.processNotificationType.itemText(i) == process.notification_type:
                self.processNotificationType.setCurrentIndex(i)
                break
        self.processNotificationType.currentIndexChanged.connect(self.update_notification_type)

        self.processPath: QLineEdit
        self.processPath.setStatusTip('Path to the executable to watch')
        self.processPathBtn: QToolButton
        self.processPathBtn.setStatusTip('Path to the executable to watch')
        self.processDelete: QPushButton
        self.processDelete.setStatusTip('Permanently delete this process definition')
        self.processDelete.pressed.connect(self.delete_from_profile)

        self.model = Process

        self.db_id = process.id

        # -- Update executable ProductName
        self._update_executable_product_name(process)

        self.process_path = ExecutableFields(self.profile_widget.ui, self, Process,
                                             self.profile_widget.ui.session, self.db_id,
                                             self.processPath, self.processPathBtn,
                                             process.executable, process.path, self.processIconLabel)
        self.process_path.executable_changed.connect(self.executable_updated)

        self.setWindowTitle(process.name)
        self.processName.setText(process.name)

    def ask_on_delete(self):
        msg_box = AskToContinue(self.profile_widget.ui)

        if not msg_box.ask('Delete Process',
                           'Do you really want to permanently delete this Process entry?',
                           'Delete', 'Cancel'):
            # User wants to abort action
            return False
        return True

    def delete_from_profile(self):
        if self.profile_widget.ui.ready():
            if not self.ask_on_delete():
                return
            if self.profile_widget.remove_db_process_entry(self.db_id):
                self.profile_widget.remove_process_widget(self)

    def update_notification_type(self, index):
        value = self.processNotificationType.itemText(index)
        update_db_entry(self.profile_widget.ui.session, Process, self.db_id, 'notification_type', value)

    def update_process_name(self, name: str):
        update_db_entry(self.profile_widget.ui.session, Process, self.db_id, 'name', name)

    def executable_updated(self):
        """ Called when the executable path was changed """
        process = self.profile_widget.ui.session.query(Process).get(self.db_id)
        self._update_executable_product_name(process)
        self.setWindowTitle(process.name)
        self.processName.setText(process.name)

    def _update_executable_product_name(self, process):
        """ Get the ProductName info from executable and updates this Process Name """
        if not process.executable:
            return

        exe_path = Path(process.path) / process.executable
        if not exe_path.exists():
            return

        product_name = ''
        try:
            file_props = get_file_properties(str(WindowsPath(exe_path)))
            file_info = file_props.get('StringFileInfo', dict())
            product_name = file_info.get('ProductName') or 'No Product Info'
            if file_props.get('FileVersion'):
                product_name = f'{product_name} - v{file_props.get("FileVersion")}'
        except Exception as e:
            logging.error('Error getting process executable ProductName: %s', e)

        if product_name:
            process.name = product_name
            self.update_process_name(product_name)
