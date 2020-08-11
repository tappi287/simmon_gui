from __future__ import unicode_literals

import ctypes
import ctypes.util
import logging
from pathlib import Path, WindowsPath

import pywintypes
import win32api
import win32con

from shared_modules.globals import get_settings_dir

# memcpy used to copy data from resource storage to our buffer
libc = ctypes.windll.msvcrt
libc.memcpy.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
libc.memcpy.restype = ctypes.c_char_p


def read_executable_icon(exe_path: Path):
    # WARNING: Assumed that icon_name - VALID resource ID
    # It can be determined in loop when enumerating resources:
    # if exception at CreateIconFromResource raised than this code appropriate
    # otherwise resource is standard icon and first code snippet can be used.
    # If resources Id exactly known then it can be hardcoded as in this code
    icon_name = 1

    # All Windows backslashes must be escaped to LoadLibrary worked correctly '\' -> '\\'
    exe_path = str(WindowsPath(exe_path.resolve()))

    try:
        hlib = win32api.LoadLibrary(exe_path)

        # This part almost identical to C++
        hResInfo = ctypes.windll.kernel32.FindResourceW(hlib, icon_name, win32con.RT_ICON)
        size = ctypes.windll.kernel32.SizeofResource(hlib, hResInfo)
        rec = win32api.LoadResource(hlib, win32con.RT_ICON, icon_name)
        mem_pointer = ctypes.windll.kernel32.LockResource(rec)

        # And this is some differ (copy data to Python buffer)
        binary_data = (ctypes.c_ubyte * size)()
        libc.memcpy(binary_data, mem_pointer, size)

        # Save it
        file = get_settings_dir() / 'icon.png'
        with open(file.as_posix(), "wb") as test_file:
            test_file.write(bytearray(binary_data))

        return file

    except pywintypes.error as error:
        logging.error("ERROR: %s" % error.strerror)
