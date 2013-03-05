
import os
import re
import signal
import shutil
import tempfile
import logging
import subprocess
import time
import unittest
import uuid
import getpass
import platform

import paasmaker
from ..common.testhelpers import TestHelpers
from manageddaemon import ManagedDaemon, ManagedDaemonError

import tornado.testing
import tornadoredis

class MySQLDaemonError(ManagedDaemonError):
    def __init__(self, cmd, returncode, working_dir):
        self.returncode = returncode
        self.working_dir = working_dir
        self.cmd = cmd
    def __str__(self):
        return "Error starting MySQL daemon; check that AppArmor is not preventing writes to %s - got exit status %d from %s" % (self.working_dir, self.returncode, self.cmd)

class MySQLDaemon(ManagedDaemon):
	"""
	A class to start and manage a MySQL daemon with a custom
	data directory.

	Note that this implementation is incomplete: among other bugs,
	MySQL's permissions are not set up correctly, so any user can
	connect without a password.

	.. warning::
	   On Ubuntu, `AppArmor <https://wiki.ubuntu.com/AppArmor>`_ is
	   configured by default to prevent mysqld from writing outside
	   of ``/var``, which will prevent this service from starting.
	   You will have to add Paasmaker's scratch directory to
	   ``/etc/apparmor.d/usr.sbin.mysqld`` like so::
	   		/path/to/paasmaker/scratch/ r,
  			/path/to/paasmaker/scratch/** rwk,
	"""
	def _eat_output(self):
		return open("%s/%s" % (self.parameters['working_dir'], str(uuid.uuid4())), 'w')

	def configure(self, working_dir, port, bind_host, password=None):
		"""
		Configure this instance.

		:arg str working_dir: The working directory for this instance.
		:arg int port: The port to listen on.
		:arg str bind_host: The address to bind to.
		:arg str|None password: The optional password to
			set as the root password.
		"""
		self.parameters['working_dir'] = working_dir
		self.parameters['port'] = port
		self.parameters['host'] = bind_host
		self.parameters['password'] = password

		# Create the working dir. If this fails, let it bubble up.
		if not os.path.exists(working_dir):
			os.makedirs(working_dir)

		# Set up a new database with mysql_install_db; we have to change
		# permissions because that script assumes it's running as root.
		command_line = [
			'mysql_install_db',
			'--datadir=' + working_dir,
			'--user=%s' % getpass.getuser(),
			'--skip-name-resolve'
		]

		if platform.system() == 'Darwin':
			# Need to point mysql_install_db at the correct
			# "my_print_defaults" path.
			# NOTE: This is not Async; but OSX is not a production
			# platform.
			homebrew_prefix_path = subprocess.check_output(['brew', '--prefix', 'mysql']).strip()
			command_line.append("--basedir=%s" % homebrew_prefix_path)

		try:
			subprocess.check_call(
				command_line,
				stdout=self._eat_output(),
				stderr=self._eat_output(),
			)
		except subprocess.CalledProcessError, ex:
			raise MySQLDaemonError(ex.cmd, ex.returncode, working_dir)

		self.save_parameters()

	def start(self, callback, error_callback):
		"""
		Start up the server for this instance.
		"""
		# Fire up the server.
		logging.info("Starting up MySQL server on port %d." % self.parameters['port'])

		# TODO: Security.
		initfile = os.path.join(self.parameters['working_dir'], 'mysql-init')
		open(initfile, 'w').write(
			"""UPDATE mysql.user SET Password=PASSWORD('%s') WHERE User='root';
			FLUSH PRIVILEGES;""" % self.parameters['password']
		)

		command_line = [
			'mysqld',
			'--datadir=' + self.parameters['working_dir'],
			'--bind-address=' + self.parameters['host'],
			'--port=' + str(self.parameters['port']),
			'--socket=' + os.path.join(self.parameters['working_dir'], 'mysqld.sock'),
			'--pid-file=' + os.path.join(self.parameters['working_dir'], 'mysqld.pid'),
			'--init-file=' + initfile
		]
		flat_command_line = " ".join(command_line)

		subprocess.check_call(
			flat_command_line + " > /dev/null 2>&1 &",
			shell=True
		)

		# Wait for the port to come into use.
		self.configuration.port_allocator.wait_until_port_used(
			self.configuration.io_loop,
			self.parameters['port'],
			5,
			callback,
			error_callback
		)

	def get_pid_path(self):
		return os.path.join(self.parameters['working_dir'], 'mysqld.pid')

	def is_running(self, keyword=None):
		return super(MySQLDaemon, self).is_running('mysqld')

	def destroy(self):
		"""
		Destroy this instance of mysql, removing all assigned data.
		"""
		# Hard shutdown - we're about to delete the data anyway.
		self.stop(signal.SIGKILL)
		shutil.rmtree(self.parameters['working_dir'])

class MySQLDaemonTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(MySQLDaemonTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, [], io_loop=self.io_loop)

	def tearDown(self):
		if hasattr(self, 'server'):
			self.server.destroy()
		self.configuration.cleanup()
		super(MySQLDaemonTest, self).tearDown()

	def test_basic(self):
		self.server = MySQLDaemon(self.configuration)
		self.server.configure(
			self.configuration.get_scratch_path_exists('mysql'),
			self.configuration.get_free_port(),
			'127.0.0.1'
		)
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start MySQL server.")

		self.assertTrue(self.server.is_running())

		self.server.stop()

		# Give it a little time to stop.
		time.sleep(2)
		self.assertFalse(self.server.is_running())

		# Start it again.
		self.server.start(self.stop, self.stop)
		result = self.wait()

		self.assertIn("In appropriate state", result, "Failed to start MySQL server.")

		self.assertTrue(self.server.is_running())