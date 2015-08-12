"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
from distutils.command.install import install as DistutilsInstall
# To use a consistent encoding
from codecs import open
from os import path

import subprocess

here = path.abspath(path.dirname(__file__))

class BuildAndInstall(DistutilsInstall):
    def run(self):
        subprocess.check_call(['make', '-C', 'client'])
        DistutilsInstall.run(self)

setup(
    cmdclass={'install': BuildAndInstall},

    name='pyseidon',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='0.0.1',

    description='A boot-once, run-many-times framework for Python',
    long_description='Pyseidon allows you to boot a Python master process, and then run clients that are forked directly from the master. This is particularly useful for completing a slow data-loading process once and then running many experiments.',

    # The project's main homepage.
    url='https://github.com/gdb/pyseidon',

    # Author details
    author='Greg Brockman',
    author_email='gdb@gregbrockman.com',

    # Choose your license
    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2.7',
    ],

    # What does your project relate to?
    keywords='pyseidon',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    scripts=['client/pyseidon']
)