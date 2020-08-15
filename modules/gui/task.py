import logging
from pathlib import Path, WindowsPath
from typing import List

from qtpy.QtWidgets import QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit, QPushButton, QToolButton, QWidget

from shared_modules.models import Condition, Gate, Process, Task
from shared_modules.taskmanager import TaskManager
from .addentrymenu import AddEntryMenu
from .condition import ConditionButton, ConditionWidget, GateButton
from .guiutil import AskToContinue, ExecutableFields, remove_from_db, update_db_entry
from ..path_util import SetDirectoryPath
from ..ui_loader import SetupWidget


class TaskWidget(QWidget):
    def __init__(self, profile_widget, task: Task):
        """

        :param modules.gui.profile.ProfileWidget profile_widget:
        :param task:
        """
        super(TaskWidget, self).__init__(profile_widget)
        self.ui = profile_widget.ui
        self.profile_widget = profile_widget

        SetupWidget.from_ui_file(self, 'task_widget.ui')

        self.commandLabel: QLabel
        self.commandLine: QLineEdit
        self.commandLine.setStatusTip('Additional arguments to send to the executable')
        if task.command:
            self.commandLine.setText(task.command)
        self.commandLine.editingFinished.connect(self.update_command)

        self.commandStop: QComboBox
        self.commandStop.setStatusTip('If the task process should be started or stopped. CAUTION: stop is terminating '
                                      'the process! Try if you can stop the process with a '
                                      'command line argument first!')
        self.commandStop.setCurrentIndex(1 if task.stop else 0)
        self.commandStop.currentIndexChanged.connect(self.update_stop_state)

        # -- Setup add Condition Menu --
        self.add_condition_menu = AddEntryMenu(self.ui,
                                               Condition,
                                               self.add_condition,
                                               self.add_condition_widget,
                                               task_id=task.id)

        # -- Setup add Condition Buttun --
        self.conditionBox: QGroupBox
        self.addConditionBtn: QPushButton
        self.addConditionBtn.setStatusTip('Add a new condition')
        self.addConditionBtn.setMenu(self.add_condition_menu)

        self.allowMultiple: QCheckBox
        self.allowMultiple.setStatusTip('Allow to start multiple instances of this process. Useful '
                                        'if you start this eg. for an exit cli argument')
        self.allowMultiple.setChecked(task.allow_multiple_instances or False)
        self.allowMultiple.stateChanged.connect(self.update_allow_multiple_state)

        self.cwdLabel: QLabel
        self.cwdPath: QLineEdit
        self.cwdPath.setStatusTip('Set the current working directory for the executable or leave empty')
        self.cwdPathBtn: QToolButton
        self.cwdPathBtn.setStatusTip('Set the current working directory for the executable or leave empty')
        self.cwd_path = SetDirectoryPath(self, mode='dir',
                                         line_edit=self.cwdPath, tool_button=self.cwdPathBtn,
                                         reject_invalid_path_edits=False)
        logging.debug('Task cwd: %s', task.cwd)
        self.cwd_path.set_path(task.cwd)
        self.cwd_path.invalid_path_entered.connect(self.update_cwd_path_empty)
        self.cwd_path.path_changed.connect(self.update_cwd_path)

        self.taskGrpBox: QGroupBox
        self.taskGrpBox.setTitle(task.name)
        self.taskGrpBox.setChecked(task.active or True)
        self.taskGrpBox.toggled.connect(self.update_task_active)
        self.taskIconLabel: QLabel
        self.taskLabel: QLabel

        self.testBtn: QPushButton
        self.testBtn.released.connect(self.task_test_run)
        self.testBtn.setStatusTip('Run the specified executable with arguments without conditions now.')

        self.taskDelete: QPushButton
        self.taskDelete.setStatusTip('Permanently delete this task')
        self.taskDelete.pressed.connect(self.delete_from_profile)
        self.taskName: QLineEdit
        self.taskName.setStatusTip('Set a task display name for your reference')
        self.taskName.setText(task.name)
        self.taskName.editingFinished.connect(self.update_task_name)

        self.wndLabel: QLabel
        self.wndMinCheckBox: QCheckBox
        self.wndMinCheckBox.setStatusTip('Start the task executable minimized (only works for OS native windows)')
        self.wndMinCheckBox.setChecked(task.wnd_minimized)
        self.wndMinCheckBox.stateChanged.connect(self.update_wnd_minimized_state)
        self.wndActCheckBox: QCheckBox
        self.wndActCheckBox.setStatusTip('Start the task executable without gaining focus '
                                         '(only works for OS native windows)')
        self.wndActCheckBox.setChecked(task.wnd_active)
        self.wndActCheckBox.stateChanged.connect(self.update_wnd_active_state)

        self.model = Task
        self.db_id = task.id
        process = task.process

        self.condition_buttons: List[ConditionButton] = list()
        self.gate_buttons: List[GateButton] = list()

        self.process_path = ExecutableFields(self.ui, self, Process, self.ui.session, task.process_id,
                                             self.processPath, self.processPathBtn,
                                             process.executable, process.path, self.taskIconLabel)
        self.setWindowTitle(task.name)

        self.refresh_conditions(task)

    def task_test_run(self):
        """ Run the defined executable without conditions """
        task = self.ui.session.query(Task).get(self.db_id)

        if self.ui.ready():
            if task.stop:
                logging.debug('User requests testing of stop Task %s', task.name)
                TaskManager.stop_task(task)
            else:
                logging.debug('User requests testing of start Task %s', task.name)
                TaskManager.start_task(task)

    def ask_on_delete(self):
        msg_box = AskToContinue(self.ui)

        if not msg_box.ask('Delete Task',
                           'Do you really want to permanently delete this Task?',
                           'Delete', 'Cancel'):
            # User wants to abort action
            return False
        return True

    def delete_from_profile(self):
        if self.ui.ready():
            if not self.ask_on_delete():
                return
            if self.profile_widget.remove_db_task_entry(self.db_id):
                self.profile_widget.remove_task_widget(self)

    def refresh_conditions(self, task: Task):
        while self.condition_buttons:
            condition_btn: ConditionButton = self.condition_buttons[-1]
            self.remove_condition_widget(condition_btn)
            self.remove_db_condition_entry(condition_btn.widget.db_id)

        # Sort Conditions and Gates
        def k(e): return e.order
        gates = [g for g in task.gates]
        gates.sort(key=k)
        conditions = [c for c in task.conditions]
        conditions.sort(key=k)

        for condition in conditions:
            if len(self.condition_buttons) >= 1:
                if gates:
                    self.add_gate_widget(gates.pop(0))
                else:
                    self.add_gate_widget(self.add_db_gate_entry())

            self.add_condition_widget(condition, True)

    def add_condition(self):
        """ Add db entry and widget """
        if self.ui.ready():
            self.add_condition_widget(self.add_db_condition_entry())

    def add_gate_widget(self, gate: Gate):
        gate_btn = GateButton(self, gate)
        self.conditionBox.layout().addWidget(gate_btn)
        self.gate_buttons.append(gate_btn)

    def add_condition_widget(self, condition: Condition, initial_add: bool = False):
        if len(self.condition_buttons) >= 1 and not initial_add:
            self.add_gate_widget(self.add_db_gate_entry())

        condition_widget = ConditionWidget(self, condition)
        condition_btn = ConditionButton(self, condition_widget)
        condition_widget.condition_button = condition_btn
        self.conditionBox.layout().addWidget(condition_btn)
        self.condition_buttons.append(condition_btn)

        self.update_condition_order()

    def add_db_condition_entry(self):
        logging.debug('Adding Condition to Profile Id %s Task Id %s', self.profile_widget.db_id, self.db_id)
        c = Condition(task_id=self.db_id,
                      name=f'Condition_{len(self.condition_buttons):02d}',
                      process=Process(),
                      order=len(self.condition_buttons))

        self.ui.session.add(c)
        self.ui.session.commit()
        return c

    def add_db_gate_entry(self):
        logging.debug('Adding Gate to Profile Id %s Task Id %s', self.profile_widget.db_id, self.db_id)
        g = Gate(task_id=self.db_id, order=len(self.gate_buttons))
        self.ui.session.add(g)
        self.ui.session.commit()

        return g

    def remove_condition_widget(self, condition_btn: ConditionButton):
        """ Remove the widget -NOT- the db entry """
        cnd_idx = self.condition_buttons.index(condition_btn)
        self.condition_buttons.pop(cnd_idx)
        condition_btn.widget.close()
        condition_btn.widget.deleteLater()
        condition_btn.deleteLater()

        self.update_condition_order()

        if self.condition_buttons:
            self.remove_gate_widget(cnd_idx)

    def update_condition_order(self):
        """ Update Condition Order based on position of condition buttons """
        for idx, condition_btn in enumerate(self.condition_buttons):
            condition = self.ui.session.query(Condition).get(condition_btn.widget.db_id)
            condition.order = idx
        self.ui.session.commit()

    def update_gate_order(self):
        for idx, gate_btn in enumerate(self.gate_buttons):
            gate = self.ui.session.query(Gate).get(gate_btn.db_id)
            gate.order = idx
        self.ui.session.commit()

    def remove_gate_widget(self, condition_index: int):
        if self.gate_buttons:
            gate_btn = self.gate_buttons.pop(condition_index - 1)
            self.remove_db_gate_entry(gate_btn.db_id)
            gate_btn.deleteLater()

        self.update_gate_order()

    def remove_db_condition_entry(self, condition_id) -> bool:
        """ Permanently remove this Condition database instance """
        return remove_from_db(self.ui.session, Condition, condition_id)

    def remove_db_gate_entry(self, gate_id) -> bool:
        """ Permanently remove this Gate database instance """
        return remove_from_db(self.ui.session, Gate, gate_id)

    def update_task_name(self):
        self.taskGrpBox.setTitle(self.taskName.text())
        update_db_entry(self.ui.session, Task, self.db_id, 'name', self.taskName.text())

    def update_task_active(self, active: bool):
        update_db_entry(self.ui.session, Task, self.db_id, 'active', active)

    def update_stop_state(self, index: int):
        value = False if index == 0 else True
        update_db_entry(self.ui.session, Task, self.db_id, 'stop', value)

    def update_cwd_path(self, cwd_path: Path):
        value = str(WindowsPath(cwd_path))
        update_db_entry(self.ui.session, Task, self.db_id, 'cwd', value)

    def update_cwd_path_empty(self):
        update_db_entry(self.ui.session, Task, self.db_id, 'cwd', str())

    def update_command(self):
        update_db_entry(self.ui.session, Task, self.db_id, 'command', self.commandLine.text())

    def update_wnd_minimized_state(self):
        update_db_entry(self.ui.session, Task, self.db_id, 'wnd_minimized', self.wndMinCheckBox.isChecked())

    def update_wnd_active_state(self):
        update_db_entry(self.ui.session, Task, self.db_id, 'wnd_active', self.wndActCheckBox.isChecked())

    def update_allow_multiple_state(self):
        update_db_entry(self.ui.session, Task, self.db_id, 'allow_multiple_instances', self.allowMultiple.isChecked())
