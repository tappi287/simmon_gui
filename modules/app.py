import sys
from multiprocessing.shared_memory import SharedMemory
from typing import Optional

from qtpy.QtWidgets import QApplication

from shared_modules.globals import APP_FRIENDLY_NAME, SHARED_MEMORY_NAME
from .gui.ui import SimmonUi


class SimmonApp(QApplication):
    def __init__(self, version: str, db_engine, db_session):
        super(SimmonApp, self).__init__(sys.argv)
        self.setApplicationName(APP_FRIENDLY_NAME)
        self.setApplicationVersion(version)
        self.setApplicationDisplayName(f'{APP_FRIENDLY_NAME} v{version}')

        self.db_engine, self.db_session = db_engine, db_session

        self.ui = SimmonUi(self)
        self.ui.show()

    @classmethod
    def set_shared_memory_state(cls, state: bytes) -> bool:
        """ Either:
            b'READ' - watcher should re-read profiles
            b'EXIT' - watcher should exit
        """
        share = cls._get_shared_memory()

        if share is not None and len(state) == 4:
            share.buf[0:4] = state
            share.close()
            return True

        return False

    @classmethod
    def read_shared_memory(cls) -> Optional[bytes]:
        share = cls._get_shared_memory()
        if share is None:
            return

        # Copy buffer contents
        # bytes() copies the content instead of sharing the pointer to the memory buffer
        # we can therefore cleanly close the share.
        buf = bytes(share.buf[0:4])
        share.close()

        return buf

    @staticmethod
    def _get_shared_memory() -> Optional[SharedMemory]:
        try:
            share = SharedMemory(name=SHARED_MEMORY_NAME, size=4)
        except FileNotFoundError:
            return

        return share
