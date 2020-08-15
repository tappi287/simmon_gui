"""
    Utilities to read Valve's Steam Library on a Windows Machine
"""
import json
import logging
import winreg as registry
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from . import acf
from shared_modules.globals import get_default_profiles_dir


STEAM_LIBRARY_FOLDERS = 'LibraryFolders'
STEAM_LIBRARY_FILE = 'libraryfolders.vdf'
STEAM_APPS_FOLDER = 'steamapps'
STEAM_APPS_INSTALL_FOLDER = 'common'


class SteamApps:
    def __init__(self):
        self.steam_apps, self.known_apps = self.find_installed_steam_games()
        self.steam_app_names = {m.get('name'): app_id for app_id, m in self.steam_apps.items() if isinstance(m, dict)}

    def find_game_location(self, app_id: int = 0, app_name: str = ''):
        """ Shorthand method to search installed apps via either id or name """
        if app_name:
            name_hits = [n for n in self.steam_app_names.keys() if n.startswith(app_name)]
            if name_hits:
                app_id = self.steam_app_names.get(name_hits[0])

        if app_id is None or app_id == 0:
            return

        m = self.steam_apps.get(app_id)

        for lib_folder in self.steam_apps.get(STEAM_LIBRARY_FOLDERS, list()):
            app_folder = lib_folder / STEAM_APPS_INSTALL_FOLDER / m.get('installdir')

            if app_folder.exists():
                return app_folder

    @staticmethod
    def find_steam_location() -> Optional[str]:
        try:
            key = registry.OpenKey(registry.HKEY_CURRENT_USER, "Software\Valve\Steam")
        except FileNotFoundError as e:
            logging.error(e)
            return None

        return registry.QueryValueEx(key, "SteamPath")[0]

    @classmethod
    def find_steam_libraries(cls) -> Optional[List[Path]]:
        """ Return Steam Library Path's as pathlib.Path objects """
        steam_apps_dir = Path(cls.find_steam_location()) / STEAM_APPS_FOLDER
        steam_lib_file = steam_apps_dir / STEAM_LIBRARY_FILE
        if not steam_lib_file.exists():
            return [steam_apps_dir]

        lib_data, lib_folders = dict(), [steam_apps_dir]
        try:
            with open(steam_lib_file.as_posix(), 'r') as f:
                lib_data = acf.load(f)
        except Exception as e:
            logging.error(f'Could not read Steam Library {steam_lib_file.name} file: {e}')

        for k, v in lib_data.get(STEAM_LIBRARY_FOLDERS, dict()).items():
            if isinstance(k, str) and k.isdigit():
                lib_dir = Path(v) / STEAM_APPS_FOLDER
                if lib_dir.exists():
                    lib_folders.append(lib_dir)

        return lib_folders

    @staticmethod
    def _add_path(manifest: dict, lib_folders):
        """ Create an 'path' key with an absolute path to the installation directory """
        p = manifest.get('installdir')
        for lib_folder in lib_folders:
            if not p:
                break
            abs_p = lib_folder / STEAM_APPS_INSTALL_FOLDER / p
            if not abs_p.exists():
                continue

            manifest['installdir'] = abs_p.as_posix()

            # Update absolute path to executable
            if manifest.get('exe_sub_path'):
                # Remove potential leading slashes
                if manifest['exe_sub_path'][0] in ('/', '\\'):
                    manifest['exe_sub_path'] = manifest['exe_sub_path'][1:]
                manifest['path'] = Path(abs_p / manifest['exe_sub_path']).as_posix()
            else:
                manifest['path'] = abs_p.as_posix()

    def find_installed_steam_games(self) -> Tuple[dict, dict]:
        steam_apps, known_apps = dict(), dict()
        lib_folders = self.find_steam_libraries()
        if not lib_folders:
            return steam_apps, known_apps

        for lib in lib_folders:
            for manifest_file in lib.glob('appmanifest*.acf'):
                try:
                    with open(manifest_file.as_posix(), 'r') as f:
                        manifest = acf.load(f)
                        if manifest is not None:
                            manifest = manifest.get('AppState')
                            steam_apps[manifest.get('appid')] = manifest
                            self._add_path(manifest, lib_folders)
                except Exception as e:
                    logging.error('Error reading Steam App manifest: %s %s', manifest_file, e)

        # -- Update entries where we exactly know the path to the executable
        try:
            known_apps_file = Path(get_default_profiles_dir()) / 'known_apps.json'
            with open(known_apps_file.as_posix(), 'r') as f:
                known_apps = json.load(f)
        except Exception as e:
            logging.error('Error reading known apps: %s', e)

        for app_id, entry_dict in known_apps.items():
            if app_id in steam_apps:
                known_apps[app_id].update(steam_apps[app_id])

            # -- Get install dir with special method for eg. CrewChief non steam app
            if 'simmon_method' in entry_dict.keys():
                method = getattr(KnownAppsMethods, entry_dict.get('simmon_method'))
                args = entry_dict.get('simmon_method_args')

                if callable(method):
                    entry_dict['installdir'] = method(*args)
                    entry_dict['path'] = Path(Path(entry_dict['installdir']) / entry_dict['exe_sub_path']).as_posix()

            # -- Update install dir to an absolute path if not already absolute
            self._add_path(entry_dict, lib_folders)

        steam_apps[STEAM_LIBRARY_FOLDERS] = lib_folders
        return steam_apps, known_apps


class KnownAppsMethods:
    @staticmethod
    def find_by_registry_keys(keys: Iterable) -> Optional[str]:
        key = None

        for key_url in keys:
            try:
                key = registry.OpenKey(registry.HKEY_LOCAL_MACHINE, key_url)
                break
            except FileNotFoundError as e:
                logging.error('Could not locate registry key %s: %s', key_url, e)

        if not key:
            return None

        return registry.QueryValueEx(key, "InstallLocation")[0]
