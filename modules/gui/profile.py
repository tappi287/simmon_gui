import logging
import os
from pathlib import Path

from qtpy.QtWidgets import QCheckBox, QLineEdit, QPushButton, QWidget

from modules.gui.addentrymenu import AddEntryMenu
from shared_modules.models import Condition, Process, Profile, Task
from .expandable_widget import ExpandableWidget
from .file_dialog import FileDialog
from .guiutil import AskToContinue, remove_from_db, update_db_entry
from .process import ProcessWidget
from .task import TaskWidget
from ..import_export import ProfileImportExport
from ..ui_loader import SetupWidget


class ProfileWidget(QWidget):
    def __init__(self, ui, profile: Profile):
        """ Profile Widget Container containing all sub
            process and task widgets.

        :param modules.gui.ui.SimmonUi ui:
        :param profile:
        """
        super(ProfileWidget, self).__init__(ui)
        self.ui = ui

        SetupWidget.from_ui_file(self, 'profile_widget.ui')

        self.profileName: QLineEdit
        self.profileName.setText(profile.name)
        self.profileName.editingFinished.connect(self.update_profile_name)

        self.profileActive: QCheckBox
        self.profileActive.setChecked(profile.active)
        self.profileActive.stateChanged.connect(self.update_profile_active_state)

        self.exportButton: QPushButton
        self.exportButton.setStatusTip('Export this Profile to a file ...')
        self.exportButton.pressed.connect(self.export)

        # -- Setup expandable process box
        self.processBox: QWidget
        self.processExpandBtn: QPushButton
        self.process_expand_widget = ExpandableWidget(self.processBox, self.processExpandBtn)

        # -- Setup expandable task box
        self.taskBox: QWidget
        self.taskExpandBtn: QPushButton
        self.task_expand_widget = ExpandableWidget(self.taskBox, self.taskExpandBtn)

        self.processAddBtn: QPushButton
        self.processAddBtn.pressed.connect(self.add_new_process)

        # -- Setup add Task menu --
        self.add_task_menu = AddEntryMenu(ui, Task, self.add_new_task, self.add_task_widget, profile_id=profile.id)
        self.taskAddBtn: QPushButton
        self.taskAddBtn.setMenu(self.add_task_menu)

        self.process_widgets = list()
        self.task_widgets = list()

        self.model = Profile
        self.db_id = profile.id
        self.setWindowTitle(profile.name)

        self.refresh_profile(profile)

    def export(self):
        path, file_type = FileDialog.save(self, directory=Path(os.path.expanduser('~')), file_key='json')
        logging.debug('Set export path to %s', path)
        profile = self.ui.session.query(Profile).get(self.db_id)
        ProfileImportExport.export(profile, Path(path))

    def ask_on_close(self):
        msg_box = AskToContinue(self.ui)

        if not msg_box.ask('Delete Profile',
                           'Do you really want to permanently delete this profile?',
                           'Delete', 'Cancel'):
            # User wants to abort close action
            return False

        self.ui.remove_db_profile_entry(self.db_id)
        return True

    def refresh_profile(self, profile: Profile):
        """ Re-Create Widget content """
        while self.process_widgets:
            self.remove_process_widget(self.process_widgets[-1])
        while self.task_widgets:
            self.remove_task_widget(self.task_widgets[-1])

        for process in profile.processes:
            self.add_process_widget(process)
        for task in profile.tasks:
            self.add_task_widget(task)

    def update_profile_name(self):
        update_db_entry(self.ui.session, Profile, self.db_id, 'name', self.profileName.text())
        self.setWindowTitle(self.profileName.text())
        index = self.ui.profileTabWidget.indexOf(self)
        self.ui.profileTabWidget.setTabText(index, self.profileName.text())

    def update_profile_active_state(self):
        update_db_entry(self.ui.session, Profile, self.db_id, 'active', self.profileActive.isChecked())

    # --- Processes ---
    def add_new_process(self) -> None:
        """ Add db entry and widget """
        if self.ui.ready():
            self.add_process_widget(self.add_db_process_entry())

    def add_db_process_entry(self) -> Process:
        p = Process(name=f'Process_{len(self.process_widgets):02d}', profile_id=self.db_id)
        self.ui.session.add(p)
        self.ui.session.commit()
        return p

    def add_process_widget(self, process: Process):
        process_widget = ProcessWidget(self, process)
        self.processBox.layout().addWidget(process_widget)
        self.processBox.resize(self.processBox.sizeHint())
        self.process_widgets.append(process_widget)

    def remove_process_widget(self, process_widget: ProcessWidget):
        """ Remove the widget -NOT- the db entry """
        self.process_widgets.remove(process_widget)
        self.processBox.layout().removeWidget(process_widget)
        process_widget.deleteLater()

    def remove_db_process_entry(self, process_id: int) -> bool:
        return remove_from_db(self.ui.session, Process, process_id)

    # --- Tasks ---
    def add_new_task(self):
        """ Add db entry and widget """
        if self.ui.ready():
            self.add_task_widget(self.add_db_task_entry())

    def add_db_task_entry(self) -> Task:
        t = Task(name=f'Task_{len(self.task_widgets)}', process=Process(),
                 profile_id=self.db_id)
        self.ui.session.add(t)
        self.ui.session.commit()
        return t

    def add_task_widget(self, task: Task):
        task_widget = TaskWidget(self, task)
        self.taskBox.layout().addWidget(task_widget)
        self.taskBox.resize(self.taskBox.sizeHint())

        self.task_widgets.append(task_widget)

    def remove_task_widget(self, task_widget: TaskWidget):
        """ Remove the widget -NOT- the db entry """
        self.task_widgets.remove(task_widget)
        self.taskBox.layout().removeWidget(task_widget)
        task_widget.deleteLater()

    def remove_db_task_entry(self, task_id: int) -> bool:
        # - Remove associated conditions
        conditions = self.ui.session.query(Condition).filter_by(task_id=task_id)
        for condition in conditions:
            remove_from_db(self.ui.session, Condition, condition.id)

        return remove_from_db(self.ui.session, Task, task_id)
