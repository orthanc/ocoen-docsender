from setuptools.config import read_configuration

import pip

config_dict = read_configuration('setup.cfg')
deps = config_dict['options']['install_requires']

pip.main(['install', *deps])
