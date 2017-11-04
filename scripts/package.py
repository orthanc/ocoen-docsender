from datetime import datetime
from setuptools.config import read_configuration

import logging
import os
import pip
import sys

start_time = datetime.now()

build_dir = sys.argv[1]
dest_dir = 'lambda'
constraints_file = 'constraints.txt'

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
root_logger.addHandler(ch)

logger = logging.getLogger(__name__)

config_dict = read_configuration('setup.cfg')
module_name = config_dict['metadata']['name']
module_version = config_dict['metadata']['version']

logger.info("Packaging '%s' version '%s' into directory '%s' with constraints '%s'.",
            module_name, module_version, dest_dir, constraints_file)

os.makedirs(dest_dir, exist_ok=True)
built_module = build_dir + '/' + module_name + '-' + module_version + '.zip'

logger.info("Installing '%s' and dependencies to '%s'.", built_module, dest_dir)
pip.main(['install', '-t' + dest_dir, '-c' + constraints_file, built_module])

end_time = datetime.now()
elapsed_time = end_time - start_time
logger.info("Packaging %s:%s to %s completed in %s.", module_name, module_version, dest_dir, elapsed_time)
