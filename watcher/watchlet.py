import asyncio
import logging
import threading
import time
from queue import Empty, Queue
from typing import List, Iterable

import pythoncom

from shared_modules.models import Process
from watcher.process_watcher import ProcessWatcher
from shared_modules.taskmanager import TaskManager


class Watchlet(threading.Thread):
    watcher_timeout_secs = ProcessWatcher.wmi_watcher_timeout * 0.001

    def __init__(self, process_list: List[Process], notification_type: str, exit_event: threading.Event):
        super(Watchlet, self).__init__()
        self.process_list = process_list
        self.notification_type = notification_type
        self.exit_event = exit_event

    def run(self) -> None:
        process_names = {p.executable for p in self.process_list}

        # -- Create a watcher thread
        watcher_thread, watcher_queue, watcher_exit_event = self._create_watcher(process_names, self.notification_type)
        watcher_thread.start()

        # -- Create a second watcher thread to avoid missing events when WMI module returns from timeout
        #    Start second thread after half the wmi timeout
        time.sleep(self.watcher_timeout_secs / 2)
        watcher_thread_two, _, _ = self._create_watcher(process_names, self.notification_type,
                                                        watcher_queue, watcher_exit_event)
        watcher_thread_two.start()

        logging.debug('Started Watchlet for %s - %s', self.notification_type, process_names)

        # -- Wait for a watch result matching a profile
        pythoncom.CoInitialize()  # Do not do this in python main thread!
        try:
            asyncio.run(self.watch_loop(watcher_queue))
        except Exception as e:
            logging.fatal('Error running watchlet watch loop: %s', e)
        finally:
            pythoncom.CoUninitialize()

        # -- Join watcher thread
        self.end_watcher((watcher_thread, watcher_thread_two), watcher_exit_event)

    async def watch_loop(self, watcher_queue: Queue):
        last_event_time = time.time() - self.watcher_timeout_secs

        # - Prepare empty check_tasks task to create an awaitable dummy
        #   for the first loop iteration
        async def empty_task():
            return False
        check_tasks_task = asyncio.create_task(empty_task())

        # -- Break queue watching in between watcher restarts
        #    to listen for a global exit event
        queue_timeout = self.watcher_timeout_secs / 2

        while not self.exit_event.is_set():
            try:
                process_name, process_id = watcher_queue.get(timeout=queue_timeout)
                logging.debug('Watchlet received queue entry: %s, %s', process_name, process_id)

                # Await last task result
                if not await check_tasks_task:
                    logging.info('No active Tasks found to execute in last run.')

                # Skip doubled events from the two threads within watcher timeout
                if (time.time() - last_event_time) < self.watcher_timeout_secs:
                    logging.debug('Skipping doubled event occurrence of %s', process_name)
                    continue

                last_event_time = time.time()
                check_tasks_task = asyncio.create_task(TaskManager.find_tasks(process_name, process_id))
            except Empty:
                pass

    @staticmethod
    def _create_watcher(process_names: set, notification_type: str, queue: Queue = None, event: threading.Event = None):
        event = event or threading.Event()
        queue = queue or Queue()
        watcher_thread = ProcessWatcher(process_names, queue, notification_type, event)
        return watcher_thread, queue, event

    @staticmethod
    def end_watcher(watcher_threads: Iterable[ProcessWatcher],  watcher_exit_event):
        """ Join a running watcher thread """
        logging.info('Watchlet stop requested. Stopping watcher thread blocking.')
        watcher_exit_event.set()
        for thread in watcher_threads:
            thread.join(timeout=(thread.wmi_watcher_timeout * 0.001))
