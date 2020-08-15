from pathlib import Path

from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QShowEvent
from qtpy.QtWidgets import QAction, QComboBox, QDialog, QLabel, QLayout, QLineEdit, QMenu, QPushButton, QStatusBar, \
    QToolButton

from shared_modules.models import Condition, Gate, Process
from .guiutil import BgrAnimation, ExecutableFields, update_db_entry
from ..ui_loader import SetupWidget


class ConditionWidget(QDialog):
    def __init__(self, task_widget, condition: Condition):
        """

        :param modules.gui.task.TaskWidget task_widget:
        :param condition:
        """
        super(ConditionWidget, self).__init__(task_widget)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        self.task_widget = task_widget

        SetupWidget.from_ui_file(self, 'condition_widget.ui')
        self.setModal(True)

        self.status_bar = QStatusBar(self)
        self.status_bar.messageChanged.connect(self.status_bar.showMessage)
        self.statusBarLayout: QLayout
        self.statusBarLayout.addWidget(self.status_bar)

        self._condition_button = None

        self.conditionRunning: QComboBox
        self.conditionRunning.setStatusTip('Condition is fulfilled if process is running or not running')
        self.conditionRunning.setCurrentIndex(0 if condition.running else 1)
        self.conditionRunning.currentIndexChanged.connect(self.update_running_condition)

        self.conditionLabel: QLabel
        self.conditionIconLabel: QLabel
        self.conditionNameLabel: QLabel

        self.conditionName: QLineEdit
        self.conditionName.setText(condition.name)
        self.conditionName.editingFinished.connect(self.update_condition_name)

        self.conditionDelete: QPushButton
        self.conditionDelete.setStatusTip('Permanently delete this condition')

        self.processLabel: QLabel
        self.processPath: QLineEdit
        self.processPath.setStatusTip('Path to the executable to watch')
        self.processPathBtn: QToolButton
        self.processPathBtn.setStatusTip('Path to the executable to watch')

        self.model = Condition

        self.db_id = condition.id
        self.process_path = ExecutableFields(self.task_widget.ui, self, Process,
                                             self.task_widget.ui.session, condition.process_id,
                                             self.processPath, self.processPathBtn,
                                             condition.process.executable, condition.process.path, None)

        self.setWindowTitle(condition.name)
        self.installEventFilter(self)

    @property
    def condition_button(self):
        return self._condition_button

    @condition_button.setter
    def condition_button(self, btn):
        self._condition_button = btn
        self.process_path.icon_label = btn
        self.task_widget.ui.start_get_executable_icon(
            Path(self.process_path.path) / self.process_path.executable)

    def eventFilter(self, obj, e: QEvent):
        if e.type() == QEvent.StatusTip:
            self.status_bar.showMessage(e.tip())
            return True
        return False

    def showEvent(self, show_event: QShowEvent):
        """ move Dialog to parent window center """
        dlg_center = self.rect().center()
        p = self.task_widget.window().mapToGlobal(self.task_widget.window().rect().center())
        center = p - dlg_center
        self.move(center)
        self.conditionName.setFocus()

    def update_running_condition(self, index: int):
        value = True if index == 0 else False
        update_db_entry(self.task_widget.ui.session, Condition, self.db_id, 'running', value)

    def update_condition_name(self):
        value = self.conditionName.text()
        self.setWindowTitle(value)
        update_db_entry(self.task_widget.ui.session, Condition, self.db_id, 'name', value)


class ConditionButton(QPushButton):
    def __init__(self, task_widget, condition_widget: ConditionWidget):
        """

        :param modules.gui.task.TaskWidget task_widget:
        :param modules.gui.condition.ConditionWidget condition_widget:
        """
        super(ConditionButton, self).__init__(task_widget)
        self.widget = condition_widget
        self.task_widget = task_widget
        self.setText(condition_widget.windowTitle())

        self.bgr_animation = BgrAnimation(self)

        self.widget.process_path.executable_invalid.connect(self._set_exe_invalid)
        self.widget.process_path.executable_valid.connect(self._set_exe_valid)

        # - Trigger a path update to render this button valid/invalid
        self.widget.process_path.trigger_update()

        self.pressed.connect(self.widget.show)
        self.widget.conditionName.textChanged.connect(self.setText)
        self.widget.conditionDelete.pressed.connect(self.remove_condition)

    def _set_exe_valid(self):
        self.bgr_animation.blink()

    def _set_exe_invalid(self):
        self.bgr_animation.active_pulsate()

    def remove_condition(self):
        if self.task_widget.ui.ready():
            if self.task_widget.remove_db_condition_entry(self.widget.db_id):
                self.task_widget.remove_condition_widget(self)


class GateButton(QPushButton):
    def __init__(self, task_widget, gate: Gate):
        super(GateButton, self).__init__(task_widget)
        self.task_widget = task_widget
        self.__value = True  # True = AND; False = OR
        self.db_id = gate.id

        self.value = gate.value

        self.menu = GateButtonMenu(self)
        self.setMenu(self.menu)

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self, value: bool):
        self.__value = value
        update_db_entry(self.task_widget.ui.session, Gate, self.db_id, 'value', value)

        if value:
            self.setText('AND')
        else:
            self.setText('OR')


class GateButtonMenu(QMenu):
    def __init__(self, btn: GateButton):
        super(GateButtonMenu, self).__init__(btn)
        self.btn = btn
        and_action = QAction('AND', self)
        and_action.triggered.connect(self.set_btn_and)
        or_action = QAction('OR', self)
        or_action.triggered.connect(self.set_btn_or)

        self.addActions((and_action, or_action))

    def set_btn_and(self):
        self.btn.value = True

    def set_btn_or(self):
        self.btn.value = False
