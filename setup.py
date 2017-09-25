from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='ocoen_docsender',
    version='0.1.0',
    description='Labda to email a file from S3 in response to SNS.',
    long_description=long_description,
    url='https://github.com/orthanc/ocoen_docsender',
    author='Ed Costello',
    author_email='ocoen@orthanc.co.nz',
    license='Apache',
    packages=find_packages(exclude=[
        'tests',
    ]),
    install_requires=[
        'boto3',
    ],
    extras_require={
        'dev': [
            'readme_renderer',
            'flake8',
        ],
        'test': [
            'pytest',
            'pytest-mock',
        ]
    }
)
