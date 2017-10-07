from datetime import datetime
from setuptools.config import read_configuration
from tempfile import mkdtemp
from zipfile import ZipFile, ZIP_DEFLATED

import logging
import os
import pip
import shutil
import sys

start_time = datetime.now()

build_dir = sys.argv[1]
dest_dir = 'dist'
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
try:
    temp_dir = mkdtemp()
    built_module = build_dir + '/' + module_name + '-' + module_version + '.zip'

    logger.info("Installing '%s' and dependencies to '%s'.", built_module, temp_dir)
    pip.main(['install', '-t' + temp_dir, '-c' + constraints_file, built_module])

    package_zip = dest_dir + '/lambda' + '-' + module_name + '-' + module_version + '.zip'
    logger.info("Creating '%s'.", package_zip)
    with ZipFile(package_zip, compression=ZIP_DEFLATED, mode='w') as arc:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = full_path[len(temp_dir) + 1:]
                arc.write(full_path, arcname=arcname)
finally:
    shutil.rmtree(temp_dir)

end_time = datetime.now()
elapsed_time = end_time - start_time
logger.info("Packaging %s:%s to %s completed in %s.", module_name, module_version, package_zip, elapsed_time)
