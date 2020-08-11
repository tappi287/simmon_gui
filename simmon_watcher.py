import logging
import signal
import sys
import threading

from watcher import log_listener
from watcher.watcher_app import WatcherApp
from shared_modules.globals import WATCHER_NAME
from watcher.singleton import SingleInstance

VERSION = '0.66b'

EXIT_EVENT = threading.Event()


def service_shutdown():
    logging.warning('OS Stop Signal received! Stopping Application.')
    EXIT_EVENT.set()


def main(version):
    s = SingleInstance(flavor_id='SimmonWatcherInstance')  # will sys.exit(-1) if another instance is running

    logging.info('---')
    logging.info('########################################')
    logging.info('%s v%s started', WATCHER_NAME, version)

    # Register the signal handlers
    signal.signal(signal.SIGTERM, service_shutdown)
    signal.signal(signal.SIGINT, service_shutdown)

    app = WatcherApp(EXIT_EVENT)

    try:
        app.app_loop()
    except KeyboardInterrupt:
        EXIT_EVENT.set()

    logging.debug('Service is shutting down.')
    log_listener.stop()
    print('Log listener stopped.')
    logging.shutdown()
    print('Logging shut down.')
    sys.exit(0)


if __name__ == '__main__':
    main(VERSION)
