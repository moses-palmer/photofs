# coding: utf-8

import os
import setuptools
import sys
import codecs


LIB_DIR = os.path.join(
    os.path.dirname(__file__),
    'lib')
sys.path.append(LIB_DIR)


# Information published on PyPi
PACKAGE_NAME = 'photofs'
VERSION = '1.3'
DESCRIPTION = 'Explore tagged photos from Shotwell in the filesystem'
AUTHOR = 'Moses Palmér'
PACKAGE_URL = 'https://github.com/moses-palmer/photofs'
with codecs.open(os.path.join(
        os.path.dirname(__file__),
        'README.rst'), encoding="UTF-8") as f:
    README = f.read()
with codecs.open(os.path.join(
        os.path.dirname(__file__),
        'CHANGES.rst'), encoding="UTF-8") as f:
    CHANGES = f.read()


# The author email
AUTHOR_EMAIL = 'moses.palmer@gmail.com'


def setup(**kwargs):
    setuptools.setup(
        name=PACKAGE_NAME,
        version=VERSION,
        description=DESCRIPTION,
        author=AUTHOR,
        author_email=AUTHOR_EMAIL,

        long_description=README + '\n\n' + CHANGES,

        install_requires=[
            'fusepy >=2.0.2'],
        setup_requires=[],

        url=PACKAGE_URL,

        entry_points={
            'console_scripts': ['photofs=photofs.__main__:main']},
        packages=setuptools.find_packages(LIB_DIR),
        package_dir={'': LIB_DIR},
        zip_safe=True,

        license='GPLv3',
        classifiers=[],

        **kwargs)


try:
    setup()
except Exception as e:
    try:
        sys.stderr.write(e.args[0] % e.args[1:] + '\n')
    except:
        sys.stderr.write(str(e) + '\n')
