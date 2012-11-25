
import os
import unittest

class ProcessCheck(object):
	@staticmethod
	def is_running(pid, keyword=None):
		# TODO: Obviously, this is linux specific...
		pid_path = "/proc/%d/cmdline" % pid

		if os.path.exists(pid_path):
			# Path exists, so now, if supplied, check the keyword.
			if keyword:
				# Load the contents of the cmdline file,
				# and read it's contents, then check it.
				fp = open(pid_path, 'r')
				contents = fp.read()
				fp.close()

				if keyword in contents:
					return True
				else:
					return False
			else:
				# No keyword supplied to check, so assume
				# that it's running.
				return True
		else:
			# Path does not exist, so process does not exist.
			return False

class ProcessCheckTest(unittest.TestCase):
	def test_simple(self):
		ourpid = os.getpid()

		result = ProcessCheck.is_running(ourpid)
		self.assertTrue(result, "Our process is not running.")

		result = ProcessCheck.is_running(ourpid, "python")
		self.assertTrue(result, "Our process is not running.")

		result = ProcessCheck.is_running(ourpid, "argh")
		self.assertFalse(result, "The keyword matched when it should not have.")

		result = ProcessCheck.is_running(100000)
		self.assertFalse(result, "An invalid PID number for Linux existed.")