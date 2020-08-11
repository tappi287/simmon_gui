import os

from shared_modules.log import setup_logging

# Set QtPy Env
os.putenv('QT_API', 'pyside2')


def setup_log_listener():
    listener = setup_logging()
    listener.start()
    return listener


log_listener = setup_log_listener()

