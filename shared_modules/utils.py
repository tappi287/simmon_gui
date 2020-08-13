import logging
from pathlib import Path
from typing import Iterator, List

import pywintypes
import win32api
import win32con
import win32event
import win32process
import wmi
from win32com.shell import shellcon
from win32com.shell.shell import ShellExecuteEx

from .models import Gate, Profile


def iterate_profiles(session) -> Iterator[Profile]:
    for profile in session.query(Profile).all():
        yield profile


def match_profiles(profiles: List[Profile], process_name: str):
    # -- Find profiles this executable has 'hit'
    active_profiles = list()

    for profile in profiles:
        for process in profile.processes:
            if process_name.casefold() == process.executable.casefold():
                active_profiles.append(profile)
                logging.debug('Process %s matched profile %s', process_name, profile.name)
                break

    return active_profiles


def run_as_admin(cmd, parameters, wait=True):
    showCmd = win32con.SW_HIDE
    lpVerb = 'runas'  # causes UAC elevation prompt.

    logging.info('Executing: %s %s', cmd, parameters)

    # ShellExecute() doesn't seem to allow us to fetch the PID or handle
    # of the process, so we can't get anything useful from it. Therefore
    # the more complex ShellExecuteEx() must be used.
    try:
        process_info = ShellExecuteEx(nShow=showCmd,
                                      fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                                      lpVerb=lpVerb,
                                      lpFile=cmd,
                                      lpParameters=parameters)
    except pywintypes.error as e:
        logging.error('User canceled UAC propmt')
        return

    if wait:
        process_handle = process_info['hProcess']

        # Wait until infinity
        obj = win32event.WaitForSingleObject(process_handle, win32event.INFINITE)

        # Get return code
        return_code = win32process.GetExitCodeProcess(process_handle)

        logging.debug("Process handle %s returned code %s", process_handle, return_code)
        return return_code


def get_file_properties(file_path: str):
    """
    Read all properties of the given file return them as a dictionary.
    """
    propNames = ('Comments', 'InternalName', 'ProductName',
        'CompanyName', 'LegalCopyright', 'ProductVersion',
        'FileDescription', 'LegalTrademarks', 'PrivateBuild',
        'FileVersion', 'OriginalFilename', 'SpecialBuild')

    props = {'FixedFileInfo': None, 'StringFileInfo': None, 'FileVersion': None}

    try:
        # backslash as parm returns dictionary of numeric info corresponding to VS_FIXEDFILEINFO struc
        fixedInfo = win32api.GetFileVersionInfo(file_path, '\\')
        props['FixedFileInfo'] = fixedInfo
        props['FileVersion'] = "%d.%d.%d.%d" % (fixedInfo['FileVersionMS'] / 65536,
                fixedInfo['FileVersionMS'] % 65536, fixedInfo['FileVersionLS'] / 65536,
                fixedInfo['FileVersionLS'] % 65536)

        # \VarFileInfo\Translation returns list of available (language, codepage)
        # pairs that can be used to retreive string info. We are using only the first pair.
        lang, codepage = win32api.GetFileVersionInfo(file_path, '\\VarFileInfo\\Translation')[0]

        # any other must be of the form \StringfileInfo\%04X%04X\parm_name, middle
        # two are language/codepage pair returned from above

        strInfo = {}
        for propName in propNames:
            strInfoPath = u'\\StringFileInfo\\%04X%04X\\%s' % (lang, codepage, propName)
            ## print str_info
            strInfo[propName] = win32api.GetFileVersionInfo(file_path, strInfoPath)

        props['StringFileInfo'] = strInfo
    except Exception as e:
        logging.error(e)

    return props


def is_process_running(executable_name: str) -> bool:
    c = wmi.WMI(find_classes=False)
    try:
        r = c.Win32_Process(Name=executable_name)
        if r:
            return True
    except pywintypes.com_error as err:
        logging.error(err)

    return False


class CheckConditionsGated:
    """
        Check a list of conditions with a list of logic gates:
            conditions: True, False, True
            gates: AND, OR
            -> True AND False OR True
            -> overall_result: True
    """
    @staticmethod
    def print_condition_overview(conditions: list):
        txt_block = ''
        for c in conditions:
            if isinstance(c, Gate):
                txt_block += f" {'AND' if c.value else 'OR'}"
            else:
                txt_block += f" {c}"
        txt_block = txt_block[1:]  # remove leading space

        logging.debug(f"Conditions: {txt_block}")

    @staticmethod
    def _check_condition_gate(a: bool, b: bool, gate: Gate) -> bool:
        if gate.value is True:  # AND
            if a and b:
                return True
        elif gate.value is False:  # OR
            if a or b:
                return True
        return False

    @classmethod
    def check_conditions(cls, conditions: List[bool], gates_ls: List[Gate]):
        if len(conditions) == 1:
            return conditions[0]

        condition_gate_ls = list()
        for idx, c in enumerate(conditions):
            if idx >= 1:
                condition_gate_ls.append(gates_ls.pop(0))
            condition_gate_ls.append(c)

        prev_condition, current_gate = None, None
        last_result, overall_result, idx = False, True, 0

        cls.print_condition_overview(condition_gate_ls)

        for c in condition_gate_ls:
            if isinstance(c, Gate):
                current_gate = c
                continue

            if prev_condition is None:
                prev_condition = c
                continue

            current_result = cls._check_condition_gate(prev_condition, c, current_gate)
            idx += 1
            logging.debug(
                f"#{idx} {prev_condition} {'AND' if current_gate.value else 'OR'} {c} = {current_result}")
            prev_condition = current_result
            overall_result = current_result

        return overall_result
