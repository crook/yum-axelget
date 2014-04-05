#!/usr/bin/env python
"""
Build script for yum-axelget.
"""
from setuptools import setup, find_packages

setup (name = "yum-axelget",
    version = '1.0.4',
    packages = find_packages(), 
    description = "Speed up download rate of yum with axel. ",
    author = 'Ray Chen',
    author_email = 'chenrano2002@gmail.com',
    license = 'GPLv2+',
    platforms=["Linux"],

    data_files=[('/usr/lib/yum-plugins/', ['axelget.py']),
                ('/etc/yum/pluginconf.d/', ['axelget.conf'])],

    classifiers=['License :: OSI Approved ::  GNU General Public License (GPL)',
                 'Operating System :: Unix',
                 'Programming Language :: Python',
                 ],
)
