#!/usr/bin/env python

from distutils.core import setup
from glob import glob

setup(
	name='twillonagios',
	version='1.0',
	description='Twilio Nagios',
	packages=['twilionagios', 'twisted.plugins'],
	scripts=glob('scripts/*')
)