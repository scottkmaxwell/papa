import sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    # noinspection PyPackageRequirements,PyUnresolvedReferences
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    if 'dist' in sys.argv or 'sdist' in sys.argv:
        print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()

setup(
    name="papa",
    version="1.0.0",
    packages=["papa", "papa.server", "tests"],
    author="Scott Maxwell",
    author_email="scott@codecobblers.com",
    maintainer="Scott Maxwell",
    url="https://github.com/scottkmaxwell/papa",
    description="Simple socket and process kernel",
    long_description=read_md('README.md'),
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
