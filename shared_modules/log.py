import logging
import logging.config
import sys
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from multiprocessing import Queue

from .globals import APP_NAME, DEFAULT_LOG_LEVEL, get_log_dir


def setup_logging(logger_name: str = APP_NAME, create_listener=True,
                  log_queue: Queue = Queue(-1)) -> QueueListener:
    # Track calls to this method
    print('Logging setup called: ',
          Path(sys._getframe().f_back.f_code.co_filename).name, sys._getframe().f_back.f_code.co_name)

    print('Logging setup detected production env. File handler will be used.')
    log_level = DEFAULT_LOG_LEVEL
    log_handlers = ['file', 'console']

    logging_queue = log_queue
    log_file_path = Path(get_log_dir()) / f'{logger_name}.log'

    log_conf = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(asctime)s %(thread)d-%(module)s %(levelname)s: %(message)s',
                'datefmt': '%d.%m.%Y %H:%M'
                },
            'file_formatter': {
                'format': '%(asctime)s.%(msecs)03d %(thread)d-%(module)s %(funcName)s %(levelname)s: %(message)s',
                'datefmt': '%d.%m.%Y %H:%M:%S'
                },
            },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler', 'stream': 'ext://sys.stdout', 'formatter': 'simple',
                'level': log_level
                },
            'file': {
                'level'    : 'DEBUG', 'class': 'logging.handlers.RotatingFileHandler',
                'filename' : log_file_path.absolute().as_posix(), 'maxBytes': 415000, 'backupCount': 3,
                'formatter': 'file_formatter',
                },
            'queue_handler': {
                'level': 'DEBUG', 'class': 'logging.handlers.QueueHandler',
                # From Python 3.7.1 defining a formatter will output the formatter of the QueueHandler
                # as well as the re-routed handler formatter eg. console -> queue listener
                'queue': logging_queue
                },
            },
        'loggers': {
            logger_name: {
                'handlers': log_handlers, 'propagate': False,
                },
            # Module loggers
            '': {
                'handlers': ['queue_handler'], 'propagate': False,
                }
            }
        }

    logging.config.dictConfig(log_conf)

    if create_listener:
        return setup_log_queue_listener(logging.getLogger(logger_name), logging_queue)


def setup_log_queue_listener(logger, log_queue):
    """
        Moves handlers from logger to QueueListener and returns the listener
        The listener needs to be started afterwwards with it's start method.
    """
    handler_ls = list()
    for handler in logger.handlers:
        print('Removing handler that will be added to queue listener: ', str(handler))
        handler_ls.append(handler)

    for handler in handler_ls:
        logger.removeHandler(handler)

    handler_ls = tuple(handler_ls)
    queue_handler = QueueHandler(log_queue)
    logger.addHandler(queue_handler)

    listener = QueueListener(log_queue, *handler_ls)
    listener.queue = log_queue
    return listener


def setup_logger(name):
    module_logger_name = f'{APP_NAME}.{name}'
    logging.getLogger(APP_NAME).info('Providing module with logger: %s', module_logger_name)
    return logging.getLogger(module_logger_name)


def reset_logging():
    manager = logging.root.manager
    manager.disabled = logging.NOTSET
    for logger in manager.loggerDict.values():
        if isinstance(logger, logging.Logger):
            logger.setLevel(logging.NOTSET)
            logger.propagate = True
            logger.disabled = False
            logger.filters.clear()
            handlers = logger.handlers.copy()
            for handler in handlers:
                # Copied from `logging.shutdown`.
                try:
                    handler.acquire()
                    handler.flush()
                    handler.close()
                except (OSError, ValueError):
                    pass
                finally:
                    handler.release()
                logger.removeHandler(handler)
