from shared_modules.globals import WATCHER_NAME
from shared_modules.log import setup_logging


def setup_log_listener():
    listener = setup_logging(WATCHER_NAME)
    listener.start()
    return listener


log_listener = setup_log_listener()
