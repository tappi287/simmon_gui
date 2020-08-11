import logging
from pathlib import Path, WindowsPath
from subprocess import Popen, STARTUPINFO, STARTF_USESHOWWINDOW
from typing import Optional

import win32con

from shared_modules.globals import get_current_modules_dir, WATCHER_EXE_NAME, WATCHER_TASK_NAME
from shared_modules.utils import run_as_admin


def run_silent(commands: list, timeout: int = 5) -> Optional[int]:
    info = STARTUPINFO()
    info.dwFlags |= STARTF_USESHOWWINDOW
    info.wShowWindow = win32con.SW_HIDE

    p = Popen(commands, startupinfo=info)
    r = p.communicate(timeout=timeout)
    return p.returncode


def install_watcher_task() -> Optional[int]:
    """ Register a Windows Task with highest privileges """
    watcher_exe = Path(get_current_modules_dir()) / WATCHER_EXE_NAME

    trigger = '$Trigger = New-ScheduledTaskTrigger -AtLogon'
    user = f"$User = $env:USERDOMAIN + '\\' + $env:USERNAME"
    action = f"$Action = New-ScheduledTaskAction -Execute '{str(WindowsPath(watcher_exe))}'"
    command = f'Register-ScheduledTask -TaskName "{WATCHER_TASK_NAME}" ' \
              f'-Trigger $Trigger -User $User -Action $Action -RunLevel Highest –Force'

    arguments = f"{trigger};{user};{action};{command}"
    return run_as_admin('powershell', arguments)


def uninstall_watcher_task() -> Optional[int]:
    """ Remove Windows Task """
    arguments = f'Unregister-ScheduledTask "{WATCHER_TASK_NAME}" -Confirm:$false'
    result = run_as_admin('powershell', arguments)
    logging.debug('Uninstall Task result: %s', result)
    return result


def start_watcher_task() -> bool:
    result = run_silent(['powershell', f'Start-ScheduledTask -TaskName "{WATCHER_TASK_NAME}"'])
    if not result or result != 0:
        return False
    return True


def find_installed_watcher_task() -> bool:
    """ Check if Windows Task exists """
    result = run_silent(['powershell', f'Get-ScheduledTask "{WATCHER_TASK_NAME}"'])

    if result is None or result != 0:
        return False
    logging.debug('Found installed Watcher Windows Task')
    return True
