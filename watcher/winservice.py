import logging
import os
import sys
import threading
import time

import pythoncom
import servicemanager
import win32api
import win32event
import win32service
import win32serviceutil
import winerror

from watcher.watcher_app import WatcherApp
from shared_modules.globals import APP_NAME, APP_FRIENDLY_NAME
from simmon_watcher import VERSION
from . import setup_log_listener


class SMWinservice(win32serviceutil.ServiceFramework):
    """ Base class to create a Windows service in Python """

    _svc_name_ = 'PythonWindowsService'
    _svc_display_name_ = f'Python Windows Service'
    _svc_description_ = 'Python Service Description'

    @classmethod
    def parse_command_line(cls):
        """
        ClassMethod to parse the command line
        """
        win32serviceutil.HandleCommandLine(cls)

    def __init__(self, args):
        """ Constructor of the winservice """
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        logging.debug('Windows Service initialized')

    def SvcStop(self):
        """ Called when the service is asked to stop """
        logging.debug('Windows Service about to stop')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.stop()

        # Write a stop message.
        servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, '')
                )

    def SvcDoRun(self):
        """ Called when the service is asked to start """
        logging.debug('Windows Service about to start')
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        self.start()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self.main()

        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
        logging.debug('Windows Service SvcDoRun end reached')

    def start(self):
        """
        Override to add logic before the start
        eg. running condition
        """
        pass

    def stop(self):
        """
        Override to add logic before the stop
        eg. invalidating running condition
        """
        pass

    def main(self):
        """
        Main class to be overridden to add logic
        """
        pass


SUCCESS = winerror.ERROR_SUCCESS
FAILURE = -1
WORKING_DIR_OPT_NAME = 'working_dir'
MAX_STATUS_CHANGE_CHECKS = 1
STATUS_CHANGE_CHECK_DELAY = 10


class WinServiceManager:
    # pass the class, not an instance of it!
    def __init__(self, service_class, service_exe_name=None):
        self.service_class = service_class
        # Added for pyInstaller v3
        self.service_exe_name_ = service_exe_name

    @staticmethod
    def is_standalone_context():
        # Changed for pyInstaller v3
        return not (sys.argv[0].endswith(".py"))

    def dispatch(self):
        if self.is_standalone_context():
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(self.service_class)
            servicemanager.Initialize(self.service_class._svc_name_,
                                      os.path.abspath(servicemanager.__file__))
            servicemanager.StartServiceCtrlDispatcher()
        else:
            win32api.SetConsoleCtrlHandler(lambda x: True, True)
            win32serviceutil.HandleCommandLine(self.service_class)

    # Service management functions
    #
    # Note: all of these functions return:
    # SUCCESS when explicitly successful
    # FAILURE when explicitly not successful at their specific purpose
    # winerror.XXXXXX when win32service (or related class)
    # throws an error of that nature
    # -----------------------------------------------------------------------
    #
    # Note: an "auto start" service is not auto started upon installation!
    # To install and start simultaneously, use start( autoInstall=True ).
    # That performs both actions for manual start services as well.
    def install(self):
        win32api.SetConsoleCtrlHandler(lambda x: True, True)
        # result = self.verifyInstall()
        result = FAILURE
        if result == SUCCESS or result != FAILURE:
            return result

        this_exe_path = os.path.realpath(sys.argv[0])
        this_exe_dir = os.path.dirname(this_exe_path)

        # Changed for pyInstaller v3 - which now incorrectly reports the calling exe
        # as the serviceModPath (v2 worked correctly!)
        if self.is_standalone_context():
            service_mod_path = self.service_exe_name_
        else:
            service_mod_path = sys.modules[self.service_class.__module__].__file__
        service_mod_path = os.path.splitext(os.path.abspath(service_mod_path))[0]
        service_class_path = "%s.%s" % (service_mod_path, self.service_class.__name__)
        self.service_class._svc_reg_class_ = service_class_path

        # Note: in a "stand alone context", a dedicated service exe is expected
        # within this directory (important for cases where a separate master exe
        # is managing services).
        service_exe_path = (service_mod_path + ".exe") if self.is_standalone_context() else None
        is_auto_start = self.service_class._svc_is_auto_start_
        start_opt = (win32service.SERVICE_AUTO_START if is_auto_start else
                     win32service.SERVICE_DEMAND_START)
        try:
            win32serviceutil.InstallService(
                pythonClassString=self.service_class._svc_reg_class_,
                serviceName=self.service_class._svc_name_,
                displayName=self.service_class._svc_display_name_,
                description=self.service_class._svc_description_,
                exeName=service_exe_path,
                startType=start_opt
                )
        except win32service.error as e:
            return e[0]
        except Exception as e:
            raise e

        win32serviceutil.SetServiceCustomOption(
            self.service_class._svc_name_, WORKING_DIR_OPT_NAME, this_exe_dir)
        for i in range(0, MAX_STATUS_CHANGE_CHECKS):
            result = self.verifyInstall()
            if result == SUCCESS:
                return SUCCESS
            time.sleep(STATUS_CHANGE_CHECK_DELAY)
        return result


class SimmonService(SMWinservice):
    _svc_name_ = f'{APP_NAME}Service'
    _svc_display_name_ = f'{APP_FRIENDLY_NAME} Service'
    _svc_description_ = f'SimMon Monitor Background Service v{VERSION}'

    _exe_name_ = sys.executable

    simmon_exit_event = threading.Event()

    def start(self):
        self.simmon_exit_event.clear()

    def stop(self):
        self.simmon_exit_event.set()

    def main(self):
        log_listener = setup_log_listener()
        logging.info('Simmon Service main loop starting')

        # Service is moved into background thread
        pythoncom.CoInitialize()

        try:
            app = WatcherApp(self.simmon_exit_event, self.hWaitStop)

            while not self.simmon_exit_event.is_set():
                app.app_loop()
        finally:
            pythoncom.CoUninitialize()

        log_listener.stop()
        logging.shutdown()
        logging.info('Simmon service main loop finished.')


if __name__ == '__main__':
    # Python win32 Service method - not working as interactive service -
    if len(sys.argv) == 1:
        print("service is starting...")
        print("(execute this script with '--help' if that isn't what you want)")

        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SimmonService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        print(sys.argv)
        win32serviceutil.HandleCommandLine(SimmonService, customInstallOptions=['interactive', 'startup=auto'])
