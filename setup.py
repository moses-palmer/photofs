#!/usr/bin/env python
# coding: utf8

import os
import setuptools
import sys


# Information published on PyPi
PACKAGE_NAME = 'photofs'
VERSION = '1.0'
DESCRIPTION = 'Explore tagged photos from Shotwell in the filesystem using FUSE'
AUTHOR = 'Moses Palmér'
PACKAGE_URL = 'https://github.com/moses-palmer/photofs'
with open(os.path.join(
        os.path.dirname(__file__),
        'README.rst')) as f:
    README = f.read()
with open(os.path.join(
        os.path.dirname(__file__),
        'CHANGES.rst')) as f:
    CHANGES = f.read()

SCRIPTS = ['photofs']

# The author email
AUTHOR_EMAIL = 'moses.palmer@gmail.com'


def setup(**kwargs):
    setuptools.setup(
        name = PACKAGE_NAME,
        version = VERSION,
        description = DESCRIPTION,
        author = AUTHOR,
        author_email = AUTHOR_EMAIL,

        long_description = README + '\n\n' + CHANGES,

        install_requires = [
            'fuse-python >=0.2'],
        setup_requires = [],

        url = PACKAGE_URL,

        scripts = [
            'photofs'],
        zip_safe = True,

        license = 'GPLv3',
        classifiers = [],

        **kwargs)


try:
    setup()
except Exception as e:
    try:
        sys.stderr.write(e.args[0] % e.args[1:] + '\n')
    except:
        sys.stderr.write(str(e) + '\n')
