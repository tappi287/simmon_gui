import logging
import threading
from multiprocessing.shared_memory import SharedMemory
from pathlib import Path

from shared_modules.globals import SHARED_MEMORY_NAME
from shared_modules.migrate import Session
from shared_modules.utils import iterate_profiles
from .process_watcher import ProcessWatcher
from .watchlet import Watchlet


class WatcherApp:
    def __init__(self, global_exit_event: threading.Event):
        self.global_exit_event = global_exit_event

        self.watchlets = list()
        self.watchlets_exit_event = threading.Event()

        self.share = self._create_shared_memory()

    def app_loop(self):
        while not self.global_exit_event.is_set():
            if self.re_read_requested() or not self.watchlets:
                # -- Reset Watchlets
                self.create_watchlets()

                # -- Communicate running application state
                self.share.buf[0:4] = b'RUN_'

            self.global_exit_event.wait(ProcessWatcher.wmi_polling_interval)

        self.share.close()
        self.share.unlink()
        Session.remove()

    def create_watchlets(self):
        # -- Stop running watchlets
        if self.watchlets:
            logging.debug('Shutting down Watchlets.')
            self.watchlets_exit_event.set()
            for watchlet in self.watchlets:
                watchlet.join(timeout=(ProcessWatcher.wmi_watcher_timeout * 0.0012))
                del watchlet

            if self.global_exit_event.is_set():
                logging.debug('Global Exit Event detected. Skipping Watchlet creation.')
                return

            self.watchlets_exit_event.clear()

        # -- Collect profile processes and categorize by notification_type
        process_dict = dict()

        # -- Create local session
        Session()

        for profile in iterate_profiles(Session):
            if not profile.active:
                continue

            logging.info('Profile: %s - %s', profile.id, profile.name)
            for process in profile.processes:
                # Skip non existing executables
                executable_path = Path(process.path) / process.executable
                if not executable_path.exists() or not process.executable:
                    continue

                if process.notification_type not in process_dict.keys():
                    process_dict[process.notification_type] = list()

                process_dict[process.notification_type].append(process)

        # -- Remove local session
        Session.remove()
        # -- Create a watchlet for each notification type Creation/Deletion etc.
        for notification_type, process_list in process_dict.items():
            logging.debug('Creating Watchlet of type: %s', notification_type)
            watchlet = Watchlet(process_list, notification_type, self.watchlets_exit_event)
            self.watchlets.append(watchlet)
            # Start watching
            watchlet.start()

    def re_read_requested(self) -> bool:
        """ See if other processes want us to re-read the profile database """
        if self.share.buf[0:4] == b'READ':
            return True
        elif self.share.buf[0:4] == b'EXIT':
            self.global_exit_event.set()
            return True

        return False

    @staticmethod
    def _create_shared_memory():
        state = b'RUN_'
        try:
            share = SharedMemory(name=SHARED_MEMORY_NAME, create=True, size=len(state))
        except FileExistsError:
            share = SharedMemory(name=SHARED_MEMORY_NAME, size=len(state))

        share.buf[0:len(state)] = state
        logging.info('Set shared memory to: %s', state)
        return share
