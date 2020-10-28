import logging
import sys
from multiprocessing import freeze_support

import shiboken2

from modules import log_listener
from modules.app import SimmonApp
from shared_modules.globals import APP_FRIENDLY_NAME
from shared_modules.migrate import db_engine, db_session
from ui import gui_resource

VERSION = '0.95'

# TODO: add executable/cmd param to shutdown watcher prior to installation
# TODO: update all matching executables if one process entry is updated in GUI
# TODO: try to stop processes with close/exit signal rather than terminating it


def main():
    logging.info('\n')
    logging.info('########################################')
    logging.info('%s v%s started', APP_FRIENDLY_NAME, VERSION)
    logging.info('Shiboken2: %s', shiboken2.__version__)
    gui_resource.qInitResources()
    logging.debug('Log queue: %s', log_listener.queue)
    app = SimmonApp(VERSION, db_engine, db_session, log_listener.queue)
    result = app.exec_()
    logging.info('Qt Application exited with result: %s', result)

    logging.debug('Stopping Log listener')
    log_listener.stop()
    logging.debug('Shutting down logging')
    logging.shutdown()
    print('Cleaning up Qt resources')
    gui_resource.qCleanupResources()
    print('About to SysExit', result)
    sys.exit(result)


if __name__ == '__main__':
    freeze_support()
    main()
