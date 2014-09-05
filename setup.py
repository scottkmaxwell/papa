import os
import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_description():
    with open(os.path.abspath(os.path.join(os.path.dirname(__file__), 'README.md')), 'r') as f:
        return f.read()

setup(
    name="papa",
    version="0.9.2",
    packages=["papa", "papa.server"],
    author="Scott Maxwell",
    author_email="scott@codecobblers.com",
    maintainer="Scott Maxwell",
    url="https://github.com/scottkmaxwell/papa",
    description="Simple socket and process kernel",
    long_description=get_description(),
    license="MIT",
    classifiers=["Development Status :: 5 - Production/Stable",
                 "Environment :: Console",
                 "Intended Audience :: Developers",
                 "License :: OSI Approved :: MIT License",
                 "Operating System :: MacOS :: MacOS X",
                 "Operating System :: POSIX :: Linux",
                 "Operating System :: POSIX :: BSD :: FreeBSD",
                 "Programming Language :: Python",
                 "Programming Language :: Python :: 2.6",
                 "Programming Language :: Python :: 2.7",
                 "Programming Language :: Python :: 3",
                 "Programming Language :: Python :: 3.3",
                 "Programming Language :: Python :: 3.4",
                 "Topic :: Software Development"],
    tests_require=['unittest2'] if sys.version_info[:2] == (2, 6) else [],
    test_suite="tests",
    entry_points="""\
    [console_scripts]
    papa = papa.server:main
    """,
    zip_safe=True
)
