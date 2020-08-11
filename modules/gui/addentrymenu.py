from qtpy.QtWidgets import QAction, QMenu

from shared_modules.models import Base, Condition, Process, Task


class AddEntryMenu(QMenu):
    def __init__(self, ui, base_class: Base, add_new_entry_callback: callable,
                 add_entry_widget_callback: callable, profile_id: int = None, task_id: int = None):
        """

        :param modules.gui.ui.SimmonUi ui:
        :param base_class:
        :param add_new_entry_callback:
        :param add_entry_widget_callback:
        :param profile_id: [optional] Profile Id this Menu is installed at, necessary to add tasks
        :param task_id: [optional] Task Id this Menu is installed at, necessary to add conditions
        """
        super(AddEntryMenu, self).__init__(ui)
        self.ui = ui
        self.base_class: Base = base_class
        self.profile_id: int = profile_id
        self.task_id: int = task_id
        self.add_entry_callback = add_new_entry_callback
        self.add_entry_widget_callback = add_entry_widget_callback
        self.aboutToShow.connect(self.create_entries)

    def create_entries(self):
        self.clear()
        for base_object in self.ui.session.query(self.base_class).all():
            action = QAction(base_object.name, self)
            if self.base_class.__name__ == 'Condition':
                action.triggered.connect(self.add_entry_from_template)
            elif self.base_class.__name__ == 'Task':
                action.triggered.connect(self.add_entry_from_template)
            action.base_object = base_object
            self.addAction(action)

        action = QAction(f'<Add new {self.base_class.__name__}>', self)
        action.triggered.connect(self.add_entry_callback)
        self.addAction(action)

    def add_entry_from_template(self):
        action = self.sender()

        if self.base_class.__name__ == 'Condition':
            base_object = self._copy_condition(action.base_object)
        elif self.base_class.__name__ == 'Task':
            base_object = self._copy_task(action.base_object)
        else:
            return

        self.ui.session.add(base_object)
        self.ui.session.commit()
        self.add_entry_widget_callback(base_object)

    def _copy_task(self, task_template):
        process = Process(name=task_template.process.name, executable=task_template.process.executable,
                          path=task_template.process.path)
        task = Task(name=task_template.name, cwd=task_template.cwd, command=task_template.command,
                    stop=task_template.stop, profile_id=self.profile_id, process=process,
                    wnd_minimized=task_template.wnd_minimized, wnd_active=task_template.wnd_active)
        return task

    def _copy_condition(self, condition_template):
        process = Process(name=condition_template.process.name, executable=condition_template.process.executable,
                          path=condition_template.process.path)
        condition = Condition(name=condition_template.name, running=condition_template.running,
                              task_id=self.task_id, process=process, )
        return condition
