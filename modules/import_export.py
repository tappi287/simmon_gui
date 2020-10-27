import json
import logging
from pathlib import Path, WindowsPath

from modules.steam_utils import SteamApps
from shared_modules import Condition, Gate, Process, Profile, Task
from shared_modules.migrate import Session


class ProfileImportExport:
    _count = 0
    _import_models = (Profile, Task, Condition, Gate, Process)
    auto_detected_msg_ls = list()
    steam_apps: SteamApps = None
    known_app_executables = dict()

    @staticmethod
    def export(profile: Profile, path: Path):
        try:
            data = profile.to_dict()

            with open(path.as_posix(), 'w') as f:
                json.dump(data, f, indent=4, sort_keys=True)
        except Exception as e:
            logging.error('Error exporting profile: %s', e)

    @classmethod
    def _prepare_known_apps(cls, use_known_apps: bool):
        cls.auto_detected_msg_ls = list()

        if not use_known_apps:
            return

        if cls.steam_apps is None:
            cls.steam_apps = SteamApps()

            for app_id, manifest in cls.steam_apps.known_apps.items():
                cls.known_app_executables[manifest.get('executable')] = manifest

    @classmethod
    def _update_process_locations_known_apps(cls, entry):
        """ Update path locations """
        if not isinstance(entry, Process):
            return

        # Do not alter entries that already have a valid path
        exe_path = Path(Path(entry.path) / entry.executable)
        if exe_path.is_file() and exe_path.exists():
            return

        if entry.executable in cls.known_app_executables:
            manifest = cls.known_app_executables.get(entry.executable)
            path = Path(manifest.get('path') or '')

            if path.exists():
                win_path = str(WindowsPath(path))
                entry.path = win_path
                cls.auto_detected_msg_ls.append(manifest.get('name'))
                logging.info('Updated Process Entry #%s with auto-detected location: %s', entry.id or -1, win_path)

    @classmethod
    def _get_single_foreign_attributes(cls, entry, data, use_known_apps):
        for k, v in data.items():
            if k in entry.json_foreign_attributes:
                cls._get_single_relationship(k, entry, v, use_known_apps)

    @classmethod
    def _get_single_relationship(cls, table_name, parent_entry, data, use_known_apps):
        for Model in cls._import_models:
            if Model.__tablename__ == table_name:
                entry = Model()
                entry.from_dict(data)
                if use_known_apps:
                    cls._update_process_locations_known_apps(entry)
                Session.add(entry)
                setattr(parent_entry, table_name, entry)

    @classmethod
    def _get_child_relations(cls, parent_entry, data, use_known_apps: bool):
        # -- Update Process entries based on KnownApps
        if use_known_apps:
            cls._update_process_locations_known_apps(parent_entry)

        # -- Get Children eg. profile.processes as dictionary
        child_relationships = parent_entry.get_children_lists(data)

        # -- Collect One to One Relationships
        #    eg. task.process
        cls._get_single_foreign_attributes(parent_entry, data, use_known_apps)

        # -- Collect One to Many Relationships
        #    eg. task.conditions
        for Model in cls._import_models:
            if Model.json_list_name not in child_relationships:
                continue

            children = list()
            for child_data_entry in child_relationships[Model.json_list_name]:
                child = Model()

                child.from_dict(child_data_entry)
                cls._get_child_relations(child, child_data_entry, use_known_apps)

                Session.add(child)
                Session.flush()  # generate id's
                children.append(child)

            # Add entries to parent
            setattr(parent_entry, Model.json_list_name, children)

    @classmethod
    def import_profile(cls, file: Path, use_known_apps: bool = False) -> bool:
        try:
            with open(file.as_posix(), 'r') as f:
                data = json.load(f)
        except Exception as e:
            logging.error('Error opening file for profile import: %s', e)
            return False

        # -- Read out known Apps and Steam library
        cls._prepare_known_apps(use_known_apps)

        try:
            profile_names = {p.name for p in Session.query(Profile).all()}
            while data['name'] in profile_names:
                if data['name'][-2:].isdigit():
                    cls._count += 1
                    data['name'] = f"{data['name'][:-2]}{cls._count:02d}"
                else:
                    data['name'] = f"{data.get('name')}_{cls._count:02d}"

            profile = Profile()
            profile.from_dict(data)
            Session.add(profile)
            Session.flush()  # Generate Id's

            cls._get_child_relations(profile, data, use_known_apps)

            Session.commit()
        except Exception as e:
            logging.error('Error importing profile: %s', e)
            Session.rollback()
            return False
        return True
