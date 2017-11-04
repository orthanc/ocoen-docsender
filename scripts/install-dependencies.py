from setuptools.config import read_configuration

import pip
import sys

if len(sys.argv) >= 2:
    constraints_file = sys.argv[1]
else:
    constraints_file = None

config_dict = read_configuration('setup.cfg')
deps = config_dict['options']['install_requires']

if constraints_file is None:
    pip.main(['install', *deps])
else:
    pip.main(['install', '-c' + constraints_file, *deps])
