#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import io
from setuptools import setup

with io.open('README.md', 'rt', encoding='utf8') as f:
    readme = f.read()

with io.open('jabra_link_370.py', 'rt', encoding='utf8') as f:
    version = re.search(r'__version__ = \'(.*?)\'', f.read()).group(1)

with io.open('requirements.txt', 'rt', encoding='utf-8') as f:
    requirements = f.read()

setup(
    name='jabra_link_370',
    description='Jabra Link 370 (BT to sound device adapter).',
    version=version,
    author='Laurent Almeras',
    author_email='lalmeras@gmail.com',
    license='BSD',
    url='https://github.com/lalmeras/jabra_link_370',
    download_url='https://github.com/lalmeras/jabra_link_370',
    py_modules=['jabra_link_370'],
    zip_safe=False,
    long_description=readme,
    long_description_content_type='text/markdown',
    entry_points={
        'console_scripts': [
            'jabra-link = jabra_link_370:cli'
        ]
    },
    install_requires=requirements.splitlines(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: BSD License',
        'Topic :: Utilities'
    ],
)
