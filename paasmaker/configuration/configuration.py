#!/usr/bin/env python

import paasmaker
import unittest
import os
import logging
import tempfile
import uuid
import shutil
import warnings

import dotconf
from dotconf.schema.containers import Section, Value
from dotconf.schema.types import Boolean, Integer, Float, String, Regex
from dotconf.parser import DotconfParser, yacc, ParsingError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# The Configuration Schema.
class PacemakerSection(Section):
	# Optional section.
	_meta = { 'repeat': (0, 1) }
	# If the pacemaker is enabled.
	enabled = Value(Boolean(), default=False)
	# The SQLAlchemy-ready database DSN. Required.
	dsn = Value(String())

class HeartSection(Section):
	# Optional section.
	_meta = { 'repeat': (0, 1) }
	# If the heart is enabled.
	enabled = Value(Boolean(), default=False)
	# The working directory. Required, must be set.
	working_dir = Value(String())

class MainSection(Section):
	# The HTTP port to listen on.
	http_port = Value(Integer(), default=8888)
	# The route to this node. None if it should be automatically determined.
	my_route = Value(String(), default=None)
	# Authentication token that the nodes use to communicate. Required.
	auth_token = Value(String())
	# Log directory. Very important - you should set this to a persistent location.
	log_directory = Value(String(), default="/tmp/paasmaker-logs/")
	# Server log level.
	server_log_level = Value(Regex(r'DEBUG|INFO|WARNING|CRITICAL|ERROR'), default="INFO")
	# Job log level. TODO: This might need to be upped/downed per job... needs more thinking.
	job_log_level = Value(Regex(r'/DEBUG|INFO|WARNING|CRITICAL|ERROR/'), default="INFO")

	pacemaker = PacemakerSection()
	heart = HeartSection()

class InvalidConfigurationException(Exception):
	pass

class Configuration:
	def __init__(self, configuration_file = None):
		loader = paasmaker.configuration.Loader()
		raw = loader.load(configuration_file)
		parser = DotconfParser(raw, debug=False, write_tables=False, errorlog=yacc.NullLogger())
		try:
			config = parser.parse()
		except ParsingError, ex:
			raise InvalidConfigurationException("Invalid configuration file syntax: %s" % str(ex))
		except AttributeError, ex:
			raise InvalidConfigurationException("Parser error - probably invalid configuration file syntax. %s" % str(ex))
		schema = MainSection()
		try:
			self.values = schema.validate(config)
		except dotconf.schema.ValidationError, ex:
			raise InvalidConfigurationException("Configuration is invalid: %s" % str(ex))

	def dump(self):
		logger.debug("Configuration dump:")
		# TODO: Go deeper into the values.
		for key, value in self.values.iteritems():
			logger.debug("%s: %s", key, str(value))

	def get_global(self, key):
		return self.values.get(key)

	def _has_section(self, section):
		return len(self.values._subsections[section]) > 0

	def get_section_value(self, section, key):
		"""Simple helper to fetch a key from a section. Assumes section exists."""
		return self.values._subsections[section][0].get(key)

	def is_pacemaker(self):
		return self._has_section('pacemaker') and self.get_section_value('pacemaker', 'enabled')
	def is_heart(self):
		return self._has_section('heart') and self.get_section_value('heart', 'enabled')

class ConfigurationStub(Configuration):
	"""A test version of the configuration object, for unit tests."""
	default_config = """
auth_token = '%(auth_token)s'
log_directory = '%(log_dir)s'
"""

	def __init__(self):
		# Choose filenames and set up example configuration.
		configfile = tempfile.mkstemp()
		self.params = {}

		self.params['log_dir'] = tempfile.mkdtemp()
		self.params['auth_token'] = str(uuid.uuid4())

		# Create the configuration file.
		configuration = self.default_config % self.params
		self.configname = configfile[1]
		open(self.configname, 'w').write(configuration)

		# Create the object with our temp name.
		Configuration.__init__(self, self.configname)

	def cleanup(self):
		# Remove files that we created.
		shutil.rmtree(self.params['log_dir'])
		os.unlink(self.configname)

class TestConfiguration(unittest.TestCase):
	minimum_config = """
auth_token = 'supersecret'
"""
	
	def setUp(self):
		# Ignore the warning when using tmpnam. tmpnam is fine for the test.
		warnings.simplefilter("ignore")

		self.tempnam = os.tempnam()

	def tearDown(self):
		if os.path.exists(self.tempnam):
			os.unlink(self.tempnam)

	def test_fail_load(self):
		try:
			config = Configuration('test_failure.yml')
			self.assertTrue(False, "Should have thrown IOError exception.")
		except IOError, ex:
			self.assertTrue(True, "Threw exception correctly.")

		try:
			open(self.tempnam, 'w').write("test:\n  foo: 10")
			config = Configuration(self.tempnam)
		except InvalidConfigurationException, ex:
			self.assertTrue(True, "Configuration did not pass the schema or was invalid.")

	def test_simple_default(self):
		open(self.tempnam, 'w').write(self.minimum_config)
		config = Configuration(self.tempnam)
		self.assertEqual(config.get_global('http_port'), 8888, 'No default present.')

if __name__ == '__main__':
	unittest.main()
