import sqlalchemy as db
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm.collections import InstrumentedList

Base = declarative_base()

NOTIFICATION_TYPES = ['Creation', 'Deletion', 'Operation', 'Modification']


class _JsonModel:
    # Should be overwritten by each Base class to identify InstrumentedList saved to json
    json_list_name = ''
    # Should be overwritten by each Base class with foreign key attribute names
    json_foreign_keys = tuple()
    # Overwritten - Should be the attribute name to get direct access to a related element
    # stored with a foreign key
    json_foreign_attributes = tuple()
    # Id of this Entry should be mapped to foriegn keys of children
    json_children_rel_id = ''

    @staticmethod
    def _get_attributes(entry: Base):
        return [a for a in dir(entry) if not a.startswith('_') and not callable(a) and not a.startswith('json')]

    @staticmethod
    def get_children_lists(data: dict) -> dict:
        """ Get InstrumentedList serialized to json """
        child_relationships = dict()
        for k, v in data.items():
            if isinstance(v, list):
                child_relationships[k] = v
        return child_relationships

    def _get_single_relationships(self, data: dict):
        """ Get single relationships eg. task.process = Process() """
        for foreign_attr in self.json_foreign_attributes:
            foreign_entry = getattr(self, foreign_attr)
            data[foreign_attr] = foreign_entry.to_dict()

    @classmethod
    def _model_dict_repr(cls, entry: Base):
        """ Serialize an db entry in to a dictionary """
        _attributes = cls._get_attributes(entry)
        _dict_repr = dict()
        for a in _attributes:
            _dict_repr[a] = getattr(entry, a)

        return {k: v for k, v in _dict_repr.items()
                if isinstance(v, int) or isinstance(v, bool) or isinstance(v, str)
                or isinstance(v, InstrumentedList)}

    def from_dict(self, data: dict):
        for k, v in data.items():
            if isinstance(v, (list, dict)) or k in self.json_foreign_keys or k in ('id',):
                continue
            setattr(self, k, v)

    def to_dict(self) -> dict:
        d = dict()
        for k, v in self._model_dict_repr(self).items():
            # -- Collect attributes
            if not isinstance(v, InstrumentedList):
                d[k] = v
            # -- Collect nested Object Lists
            else:
                d[k] = list()
                for entry in v:
                    sd = entry.to_dict()
                    d[k].append(sd)

        self._get_single_relationships(d)
        return d


class Profile(Base, _JsonModel):
    json_list_name = ''
    json_children_rel_id = 'profile_id'

    __tablename__ = 'profile'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, index=True)
    active = db.Column(db.Boolean, default=True)

    # One to Many relationship to Processes
    processes = relationship('Process', cascade="all, delete, delete-orphan")

    # One to Many relationship to Task(s)
    tasks = relationship('Task', cascade="all, delete, delete-orphan")


class Task(Base, _JsonModel):
    json_list_name = 'tasks'
    json_foreign_keys = ('process_id', 'profile_id',)
    json_foreign_attributes = ('process',)
    json_children_rel_id = 'task_id'

    __tablename__ = 'task'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), index=True)
    active = db.Column(db.Boolean, default=True)

    # Current working directory
    cwd = db.Column(db.String(500), default='')

    # Additional arguments
    command = db.Column(db.String(500), default='')
    stop = db.Column(db.Boolean, default=False)

    # Window Creation Flags
    wnd_minimized = db.Column(db.Boolean, default=False)
    wnd_active = db.Column(db.Boolean, default=True)

    # Allow start of multiple instance aka. allow to send eg. exit cli args by
    # starting the process multiple times
    allow_multiple_instances = db.Column(db.Boolean, default=False)

    # Many To One relationship to Process
    process_id = db.Column(db.Integer, db.ForeignKey('process.id'))
    process = relationship('Process', single_parent=True, cascade="all, delete, delete-orphan")

    # Relationship to Profile
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'))

    # One to Many relationship to Condition
    conditions = relationship('Condition', cascade="all, delete, delete-orphan")

    # One to Many relationship to Gate
    gates = relationship('Gate', cascade="all, delete, delete-orphan")


class Condition(Base, _JsonModel):
    json_list_name = 'conditions'
    json_foreign_keys = ('task_id', 'process_id')
    json_foreign_attributes = ('process',)

    __tablename__ = 'condition'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), index=True)
    order = db.Column(db.Integer, default=-1)
    running = db.Column(db.Boolean, default=True)

    # Relationship to Task
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))

    # Many To One relationship to Process
    process_id = db.Column(db.Integer, db.ForeignKey('process.id'))
    process = relationship('Process', single_parent=True, cascade="all, delete, delete-orphan")


class Gate(Base, _JsonModel):
    json_list_name = 'gates'
    json_foreign_keys = ('task_id',)

    __tablename__ = 'gate'

    id = db.Column(db.Integer, primary_key=True)
    order = db.Column(db.Integer, default=-1)
    value = db.Column(db.Boolean, default=True)  # True == AND; False == OR

    # Relationship to Task
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))


class Process(Base, _JsonModel):
    json_list_name = 'processes'
    json_foreign_keys = ('profile_id',)
    json_children_rel_id = 'process_id'

    __tablename__ = 'process'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), default='Process')
    executable = db.Column(db.String(70), index=True, default='')
    path = db.Column(db.String(500), default='')

    # Creation', 'Deletion', 'Operation', 'Modification
    notification_type = db.Column(db.String(len('Modification')), default='Creation')

    # Relationship to Profile
    profile_id = db.Column(db.Integer, db.ForeignKey('profile.id'))
