import os
from pathlib import Path, WindowsPath

import sqlalchemy as db
from alembic import command, context
from alembic.config import Config as AlembicConfig
from sqlalchemy.orm import scoped_session, sessionmaker

from .globals import SQLALCHEMY_DATABASE_URI, get_current_modules_dir
from .models import *
from .models import Base
from . import SimmonAppState
from .default_entries import create_example_entry

# Flag the app as running so alembic env.py knows not to create loggers
SimmonAppState.is_running = True

current_dir = Path(get_current_modules_dir()) / 'migrate'
alembic_ini_path = Path(get_current_modules_dir()) / 'alembic.ini'
ALEMBIC_INI = str(WindowsPath(alembic_ini_path))
MIGRATION_DIR = str(WindowsPath(current_dir))


class Config(AlembicConfig):
    def get_template_directory(self):
        return os.path.join(MIGRATION_DIR, 'templates')


CONFIG = Config(ALEMBIC_INI)
CONFIG.set_main_option('script_location', MIGRATION_DIR)


def upgrade_database(revision='head', sql=False, tag=None):
    """ Upgrade to latest version (head) """
    command.upgrade(CONFIG, revision, sql=sql, tag=tag)


def downgrade(revision='head', sql=False, tag=None):
    command.downgrade(CONFIG, revision, sql=sql, tag=tag)


def migrate(message=None, sql=False, head='head', splice=False,
            branch_label=None, version_path=None, rev_id=None):
    """ Alias for 'revision --autogenerate' """
    command.revision(CONFIG, message, autogenerate=True, sql=sql,
                     head=head, splice=splice, branch_label=branch_label,
                     version_path=version_path, rev_id=rev_id)


def init_database(debug: bool = False):
    # Migrate database to latest revision
    upgrade_database()

    engine = db.create_engine(SQLALCHEMY_DATABASE_URI)

    if debug:
        # Drop all tables
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)

    from sqlalchemy.orm import Session
    session = Session(engine)

    if debug:
        create_example_entry(session)

    return engine, session


# Migrate database
db_engine, db_session, = init_database()

session_factory = sessionmaker(bind=db_engine)
Session = scoped_session(session_factory)


if __name__ == '__main__':
    upgrade_database()
    # downgrade(revision='641ab19d8051')
