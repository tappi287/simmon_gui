import logging
import sys
import threading
import time
from queue import Queue, Empty
from typing import Union

import pythoncom
import pywintypes
import wmi


logging.basicConfig(stream=sys.stdout, format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%H:%M', level=logging.DEBUG)


class ProcessWatcher(threading.Thread):
    # -- Seconds for WITHIN Parameter
    #    we will receive updates in this interval
    wmi_polling_interval = 8

    # -- Milliseconds for one watch loop
    #    will timeout if no process event
    #    was detected within this time and restart the loop
    wmi_watcher_timeout = wmi_polling_interval * 1000 * 6  # Milliseconds

    # -- Fields we want our query to contain
    fields = ['TargetInstance', 'ProcessId', 'Name']

    def __init__(self, process_names: set, queue: Queue, notification_type: str, exit_event: threading.Event):
        """ Thread to watch for process events. Reports event to the queue until exit event is set.

        :param process_names:
        :param queue:
        :param notification_type: “creation”, “deletion”, “modification” or “operation”
        :param exit_event:
        """
        super(ProcessWatcher, self).__init__()
        self.process_names = process_names
        self.queue = queue
        self.notification_type = notification_type
        self.exit_event = exit_event

    def run(self):
        """ Watch for created processes until exit event is set """
        logging.debug('ProcessWatcher started.')
        pythoncom.CoInitialize()  # Do not do this in python main thread!
        try:
            logging.info('Started to watch for %s', self.process_names)
            self.watch_loop()
        finally:
            pythoncom.CoUninitialize()

        logging.debug('ProcessWatcher shutdown.')

    def watch_loop(self):
        # Init WMI module
        c = wmi.WMI(find_classes=False)

        logging.debug('WQL: %s', self._build_raw_wql_query())

        # -- Watch in loop
        while not self.exit_event.is_set():
            try:
                if self.process_names:
                    p = self.watch_specific(c)
                else:
                    p = self.watch_all(c)

                if p is not None:
                    logging.debug('Found %s of %s %s', self.notification_type, p.Name, p.ProcessId)
                    self.queue.put((p.Name, p.ProcessId))
            except pywintypes.com_error as err:
                logging.error(err)

    def watch_specific(self, c: wmi.WMI) -> Union[None, wmi._wmi_event]:
        """ Build the WQL query watching only for process names we are interested in """
        watcher = c.Win32_Process.watch_for(raw_wql=self._build_raw_wql_query(), fields=self.fields)

        try:
            # This will block until timeout
            event = watcher(timeout_ms=self.wmi_watcher_timeout)
            return event
        except wmi.x_wmi_timed_out:
            pass

    def watch_all(self, c: wmi.WMI) -> Union[None, wmi._wmi_event]:
        """ Let WMI module handle query creation and watch for all processes """
        watcher = c.Win32_Process.watch_for(self.notification_type)

        try:
            # This will block until timeout
            p = watcher(self.wmi_watcher_timeout)
            return p
        except wmi.x_wmi_timed_out:
            pass

    def _build_raw_wql_query(self):
        """ Build the WQL query based on process names to watch eg:
            SELECT * FROM __InstanceCreationEvent WITHIN 5 WHERE TargetInstance
            ISA 'Win32_Process' AND (TargetInstance.Name = 'calc.exe' OR TargetInstance.Name = 'notepad.exe')
        """
        field_list = ", ".join(self.fields)

        where = ''
        for process_name in self.process_names:
            where += f"TargetInstance.Name = '{process_name}' OR "

        wql = f"SELECT {field_list} FROM __Instance{self.notification_type}Event WITHIN {self.wmi_polling_interval} " \
              f"WHERE TargetInstance ISA 'Win32_Process' AND ("
        wql += f"{where[:-4]})"

        return wql


def main():
    event = threading.Event()
    q = Queue()
    start = time.time()

    watcher_thread = ProcessWatcher({'notepad++.exe', 'notepad.exe', 'code.exe'}, q, 'Creation', event)
    watcher_thread.start()

    while 1:
        try:
            try:
                p_name, pid = q.get(timeout=ProcessWatcher.wmi_polling_interval)
                logging.info('Result queue: %s, %s', p_name, pid)
            except Empty:
                logging.info('Empty queue')
            if time.time() - start > 10:
                break
        except KeyboardInterrupt:
            pass
            break

    logging.info('Sending exit event to watcher')
    event.set()
    watcher_thread.join(timeout=2.5)


if __name__ == '__main__':
    main()
