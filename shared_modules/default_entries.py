import logging

from shared_modules.models import Process, Condition, Task, Profile


def create_example_entry(session):
    procs = {('calc.exe', r'C:\Windows\System32', 'Deletion'),
             ('notepad.exe', r'C:\Windows\System32', 'Creation'),
             ('code.exe', r"C:\Program Files\Microsoft VS Code", 'Creation')}

    process_list = list()
    for idx, (executable, path, notification_type) in enumerate(procs):
        process = Process(name=executable, executable=executable, path=path, notification_type=notification_type)
        process_list.append(process)

    qt_designer_process = Process(executable='notepad.exe', path=r"C:\Windows\System32")
    c = Condition(id=0, name='QtDesigner not running', running=False, process=qt_designer_process)

    t = Task(id=0, name='Start Notepad', process=qt_designer_process, conditions=[c],
             wnd_minimized=True, wnd_active=False)

    p = Profile(id=0, name='Example Profile@§$% Test', processes=process_list, tasks=[t])
    session.add(p)
    session.commit()
    logging.info('Created example entries')
