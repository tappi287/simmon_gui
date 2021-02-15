import asyncio
import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import List

import win32con
import wmi

from .models import Task
from .utils import CheckConditionsGated, is_process_running, iterate_profiles, match_profiles
from .migrate import Session


class TaskManager:
    debug_conditions = False

    @classmethod
    async def find_tasks(cls, p_name: str, pid: str) -> bool:
        """ Find all tasks activated by the created process """
        logging.info('Found %s, %s', p_name, pid)

        # - Create local session
        Session()

        # -- Find profiles this executable has 'hit'
        active_profiles = match_profiles(list(iterate_profiles(Session)), p_name)

        # -- Collect tasks of active profiles
        tasks = list()
        for profile in active_profiles:
            tasks += profile.tasks

        # -- Find tasks whose conditions are met
        num_tries, activated_tasks, log_level = 2, list(), logging.DEBUG
        while (num_tries := num_tries - 1) >= 0 and not activated_tasks:
            for task in tasks:
                logging.debug('Run #%s Checking task: %s', 2-num_tries, task.name)

                if cls._check_task_conditions(task):
                    activated_tasks.append(task)

            # - Sometimes exiting processes take a while to be recognized as "not running"
            #   try two times if we did not found a activated task before
            await asyncio.sleep(10)

        cls._execute_tasks(activated_tasks)

        # - Remove local session
        Session.remove()
        return True if activated_tasks else False

    @classmethod
    def _execute_tasks(cls, tasks: List[Task]):
        for task in tasks:
            if task.stop:
                cls.stop_task(task)
            else:
                cls.start_task(task)

    @staticmethod
    def start_task(task: Task):
        """ Task should start a process """
        executable = Path(task.process.path) / task.process.executable
        command = [str(executable.resolve())]

        if not executable.exists():
            logging.error(f'Could not start task {task.name} executable that does not exists: f{executable.as_posix()}')
            return

        # Add arguments
        if task.command:
            for cmd in shlex.split(task.command):
                command.append(cmd)

        min = {True: 'minimized', False: 'regularly'}
        act = {True: 'active', False: 'inactive'}

        logging.info(f'Executing task: {task.name} with command: {command}. Window will be '
                     f'opened {min[task.wnd_minimized]} and set to {act[task.wnd_active]}.')

        # -- Window Creation Flags
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        if task.wnd_minimized and not task.wnd_active:
            # minimized, not active
            info.wShowWindow = win32con.SW_SHOWMINNOACTIVE
        elif task.wnd_minimized and task.wnd_active:
            # minimized, active
            info.wShowWindow = win32con.SW_SHOWMINIMIZED
        elif not task.wnd_minimized and not task.wnd_active:
            # default, not active
            info.wShowWindow = win32con.SW_SHOWNA
        else:
            # default, active
            info.dwFlags = ~subprocess.STARTF_USESHOWWINDOW
            # info.wShowWindow = win32con.SW_SHOWDEFAULT

        # -- Start process
        #    and add current working directory
        logging.debug('Window ShowWindow Flag: %s', info.wShowWindow)
        try:
            subprocess.Popen(command, cwd=task.cwd or None, startupinfo=info)
        except OSError as e:
            logging.error('Could not start executable. Probably higher privileges are required. %s', e)

        time.sleep(0.1)

    @staticmethod
    def stop_task(task: Task) -> bool:
        """ Task should stop a process """
        c = wmi.WMI(find_classes=False)
        r = c.Win32_Process(Name=task.process.executable)
        if r:
            for p in r:
                result = p.Terminate()

                if len(result) >= 1 and result[0] != 0:
                    logging.error('Task %s could not terminate process: %s', task.name, task.process.executable)
                    logging.error('Termination result: %s', result)
                    return False

                logging.debug('Task %s terminated process: %s', task.name, task.process.executable)
        else:
            logging.debug('Task %s could not find process: %s to terminate', task.name, task.process.executable)
            return False

        return True

    @staticmethod
    def _check_task_conditions(task: Task) -> bool:
        """ Check if all conditions for a task are met

        :param Task task: the task whose conditions should be tested
        :returns: True if all conditions where met. Also True if no conditions present.
        """
        if not task.active:
            logging.debug('Task %s is set in-active.', task.name)
            return False

        results = list()
        d = {False: 'is not running', True: 'is running'}

        # -- Check that task executable exists
        task_executable_path = Path(task.process.path) / task.process.executable
        if not task_executable_path.exists() or not task.process.executable:
            return False

        # -- Check that task executable is not already running/not running
        if not task.stop and not task.allow_multiple_instances and is_process_running(task.process.executable):
            logging.debug('Task %s executable already running.', task.name)
            return False
        elif task.stop and not is_process_running(task.process.executable):
            logging.debug('Task %s executable already stopped.', task.name)
            return False

        # -- Sort conditions
        def k(e): return e.order
        conditions = [c for c in task.conditions]
        conditions.sort(key=k)

        # -- Check task conditions
        for condition in conditions:
            condition_executable_path = Path(condition.process.path) / condition.process.executable

            process_running = is_process_running(condition.process.executable)
            if not condition_executable_path.exists() or not condition.process.executable:
                process_running = False

            results.append(
                condition.running == process_running
                )

            if condition.running == process_running and TaskManager.debug_conditions:
                logging.debug(f'Task {task.name} condition "if {condition.process.executable} {d[condition.running]}"'
                              f' met: {condition.process.executable} {d[process_running]}.')
            elif TaskManager.debug_conditions:
                logging.debug(f'Task {task.name} condition "if {condition.process.executable} {d[condition.running]}"'
                              f' NOT met: {condition.process.executable} {d[process_running]}.')

        gates = [g for g in task.gates]
        return CheckConditionsGated.check_conditions(results, gates, TaskManager.debug_conditions)
