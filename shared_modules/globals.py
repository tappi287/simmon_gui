import os
import logging
import sys
from pathlib import Path
from typing import Union

from appdirs import user_data_dir, user_log_dir, user_state_dir


logging.basicConfig(stream=sys.stdout, format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%H:%M', level=logging.DEBUG)

APP_NAME = 'simmon'
WATCHER_NAME = 'simmon_watcher'
SETTINGS_DIR_NAME = 'simmon'
APP_FRIENDLY_NAME = 'SimMon'
BASE_PATH = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__ + '/..')))
DEFAULT_PROFILES = 'userdata'
SHARED_MEMORY_NAME = 'simmon_share_1010287'
WATCHER_EXE_NAME = 'simmon_watcher.exe'
WATCHER_TASK_NAME = 'SimmonWatcher_StartUp'
UPDATE_VERSION_FILE = 'version.txt'
UPDATE_INSTALL_FILE = 'Simmon_Setup_{version}_win64.exe'
WIN_AUTOSTART_DIR = user_state_dir(roaming=True) + r'\Microsoft\Windows\Start Menu\Programs\Startup'

DEFAULT_LOG_LEVEL = 'DEBUG'
UI_PATH = 'ui'

# Frozen or Debugger
if getattr(sys, 'frozen', False):
    # -- Running in PyInstaller Bundle ---
    FROZEN = True
else:
    # -- Running in IDE ---
    FROZEN = False


def check_and_create_dir(directory: Union[str, Path]) -> str:
    if not os.path.exists(directory):
        try:
            os.mkdir(directory)
            logging.info('Created: %s', directory)
        except Exception as e:
            logging.error('Error creating directory %s', e)
            return ''

    return directory


def get_current_modules_dir() -> str:
    """ Return path to this app modules directory """
    return BASE_PATH


def get_default_profiles_dir() -> str:
    return os.path.join(get_current_modules_dir(), DEFAULT_PROFILES)


def get_settings_dir() -> Path:
    return Path(check_and_create_dir(user_data_dir(SETTINGS_DIR_NAME, '')))


def get_log_dir() -> str:
    log_dir = user_log_dir(SETTINGS_DIR_NAME, '')
    setting_dir = os.path.abspath(os.path.join(log_dir, '../'))
    # Create <app-name>
    check_and_create_dir(setting_dir)
    # Create <app-name>/log
    return check_and_create_dir(log_dir)


SQLALCHEMY_DATABASE_URI = f'sqlite:///{get_settings_dir().resolve().as_posix()}\\{SETTINGS_DIR_NAME}.sqlite3'
