from setuptools import setup, find_packages
from simmon import VERSION
from shared_modules.globals import APP_FRIENDLY_NAME

setup(name=APP_FRIENDLY_NAME, version=VERSION, packages=find_packages())