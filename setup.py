#!/usr/bin/python
# -*- coding:Utf-8 -*-

from setuptools import setup

setup(name='cubetoolkit',
      version='0.1',
      description='toolkit to works on cubicweb cubes',
      author='Laurent Peuch',
      long_description=open("README.md", "r").read(),
      long_description_content_type='text/markdown',
      author_email='cortex@worlddomination.be',
      url='https://github.com/Psycojoker/cubetoolkit',
      install_requires=['argh', 'redbaron', 'requests'],
      entry_points={
          'console_scripts': [
              'cubetoolkit = cubetoolkit:main',
              'ctk = cubetoolkit:main',
          ]
      },
      license='gplv3+',
      keywords='cubicweb',
      )
