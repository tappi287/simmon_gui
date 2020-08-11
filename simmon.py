import logging
import sys

import shiboken2

from modules import log_listener
from modules.app import SimmonApp
from shared_modules.globals import APP_FRIENDLY_NAME
from shared_modules.migrate import db_engine, db_session
from ui import gui_resource


VERSION = '0.75b'

# TODO: detect installed Software and add templates
# TODO: try to stop processes with close/exit signal rather than terminating it


def main():
    logging.info('\n')
    logging.info('########################################')
    logging.info('%s v%s started', APP_FRIENDLY_NAME, VERSION)
    logging.info('Shiboken2: %s', shiboken2.__version__)
    gui_resource.qInitResources()

    app = SimmonApp(VERSION, db_engine, db_session)
    result = app.exec_()

    log_listener.stop()
    logging.shutdown()
    gui_resource.qCleanupResources()

    sys.exit(result)


if __name__ == '__main__':
    main()
