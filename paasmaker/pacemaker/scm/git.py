
import os
import tempfile
import shutil
import subprocess

import paasmaker
from base import BaseSCM, BaseSCMTest

import colander

class GitSCMParametersSchema(colander.MappingSchema):
	location = colander.SchemaNode(colander.String(),
		title="Location of source",
		description="The URL to the repository.")
	branch = colander.SchemaNode(colander.String(),
		title="The Branch to use",
		description="The Git branch to use. Defaults to master.",
		missing="master",
		default="master")
	revision = colander.SchemaNode(colander.String(),
		title="The revision to use",
		description="The Git revision to use. Defaults to HEAD.",
		missing="HEAD",
		default="HEAD")

class GitSCM(BaseSCM):
	MODES = [paasmaker.util.plugin.MODE.SCM_EXPORT, paasmaker.util.plugin.MODE.SCM_CHOOSER]
	PARAMETERS_SCHEMA = {paasmaker.util.plugin.MODE.SCM_EXPORT: GitSCMParametersSchema()}

	def create_working_copy(self, callback, error_callback):
		# Make a directory to extract to. It should be persistent.
		self.path = self.get_persistent_scm_dir()
		self.callback = callback
		self.error_callback = error_callback

		self.logger.info("Working directory: %s", self.path)
		self.logger.info("Source git repo is %s", self.parameters['location'])

		worker = GitGetDirectoryUpToDate(
			self.configuration,
			self.path,
			self.parameters,
			self.logger
		)

		def git_up_to_date(path):
			# Move on to creating the output directory.
			self._create_output_directory()

		worker.start(git_up_to_date, error_callback)

	def _create_output_directory(self):
		# Now we need to create a copy of the checkout that can be altered.
		# For speed, we rsync over the top using the delete flag
		# to speed it up.
		self.output_dir = self.get_persistent_output_dir()

		self.logger.info("Creating editable working copy.")
		self.log_fp = self.logger.takeover_file()

		command = [
			'rsync',
			'--verbose',
			'--recursive',
			'--delete',
			'--exclude', '.git', # Don't copy the git metadata.
			os.path.join(self.path) + '/',
			self.output_dir
		]

		def on_command_finish(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command returned code %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			if code == 0:
				self.callback(self.output_dir, "Successfully switched to the appropriate revision.")
			else:
				self.error_callback("Unable to create a working output directory.")

		rsync = paasmaker.util.Popen(
			command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=on_command_finish,
			io_loop=self.configuration.io_loop,
			cwd=self.path
		)

	def extract_manifest(self, manifest_path, callback, error_callback):
		self.logger.info("Extracting manifest file from %s", self.parameters['location'])
		self.path = self.get_persistent_scm_dir()

		# Unfortunately, to extract the manifest file, we need to clone the whole lot.
		# So start doing that now. It does save time later though...
		worker = GitGetDirectoryUpToDate(
			self.configuration,
			self.path,
			self.parameters,
			self.logger
		)

		def git_up_to_date(path):
			# Move on to extracting the manifest file.
			self._extract_manifest_real(manifest_path, callback, error_callback)

		worker.start(git_up_to_date, error_callback)

	def _extract_manifest_real(self, manifest_path, callback, error_callback):
		# See if the file exists.
		full_manifest_path = os.path.join(self.path, manifest_path)

		if os.path.exists(full_manifest_path):
			manifest_fp = open(full_manifest_path, 'r')
			manifest = manifest_fp.read()
			manifest_fp.close()

			callback(manifest)
		else:
			error_callback('Unable to locate manifest file at the path %s' % manifest_path)

	def create_form(self):
		return """
		<label>
			Repository URL:
			<input type="text" name="location" />
		</label>
		<label>
			Branch:
			<input type="text" name="branch" />
		</label>
		<label>
			Revision:
			<input type="text" name="revision" />
		</label>
		"""

	def create_summary(self):
		return {
			'location': 'The git repository URL',
			'branch': 'The git branch to use',
			'revision': 'The git revision to use'
		}

class GitGetDirectoryUpToDate(object):
	def __init__(self, configuration, directory, parameters, logger):
		self.configuration = configuration
		self.directory = directory
		self.parameters = parameters
		self.logger = logger

	def start(self, callback, error_callback):
		self.callback = callback
		self.error_callback = error_callback

		# Is it a new folder?
		git_test = os.path.join(self.directory, '.git')
		if os.path.exists(git_test):
			# Already cloned. Just update it.
			command = [
				'git',
				'pull'
			]

			self._git_command(command, self.pull_complete)
		else:
			# Not yet cloned. Clone a new one.
			command = [
				'git',
				'clone',
				self.parameters['location'],
				'.'
			]

			self._git_command(command, self.clone_complete)

	def clone_complete(self, code):
		if code == 0:
			self.logger.info("Successfully cloned repo.")

			# Move on to checking out the appropriate revision.
			self.select_branch()
		else:
			self.error_callback("Unable to clone repo.")

	def pull_complete(self, code):
		if code == 0:
			self.logger.info("Successfully pulled repo updates.")

			# Reset the working copy.
			self.reset_working_copy()
		else:
			self.error_callback("Unable to pull repo updates.")

	def reset_working_copy(self):
		command = ['git', 'reset', '--hard', 'HEAD']
		self._git_command(command, self.reset_complete)

	def reset_complete(self, code):
		if code == 0:
			self.logger.info("Successfully reset the repo.")

			# Move on to selecting a branch.
			self.select_branch()
		else:
			self.error_callback("Unable to reset the repo.")

	def select_branch(self):
		command = ['git', 'checkout', self.parameters['branch']]
		self._git_command(command, self.select_branch_complete)

	def select_branch_complete(self, code):
		if code == 0:
			self.logger.info("Successfully switched the branch (if needed).")

			# Move on to choosing a specific revision.
			self.select_revision()
		else:
			self.error_callback("Unable to select the branch.")

	def select_revision(self):
		command = ['git', 'checkout', self.parameters['revision']]
		self._git_command(command, self.select_revision_complete)

	def select_revision_complete(self, code):
		if code == 0:
			self.logger.info("Successfully switched to the appropriate revision.")

			# And we're done.
			self.callback(self.directory)
		else:
			self.error_callback("Unable to select the revision.")

	def _git_command(self, command, callback):
		self.log_fp = self.logger.takeover_file()

		def on_command_finish(code):
			self.logger.untakeover_file(self.log_fp)
			self.logger.info("Command returned code %d", code)
			#self.configuration.debug_cat_job_log(self.logger.job_id)
			callback(code)

		git = paasmaker.util.Popen(
			command,
			stdout=self.log_fp,
			stderr=self.log_fp,
			on_exit=on_command_finish,
			io_loop=self.configuration.io_loop,
			cwd=self.directory
		)

class GitSCMTest(BaseSCMTest):
	def _run_git_command(self, command):
		try:
			result = subprocess.check_output(
				command,
				cwd=self.repo,
				stderr=subprocess.PIPE # TODO: If it errors and pushes
				# a lot of output, this will block the process...
			)
			#print result
		except subprocess.CalledProcessError, ex:
			print ex.output
			raise ex

	def setUp(self):
		super(GitSCMTest, self).setUp()

		sample_dir = os.path.normpath(os.path.dirname(__file__) + '/../../../misc/samples/tornado-simple')

		# Create an example repo.
		self.repo = tempfile.mkdtemp()

		self._run_git_command(['git', 'init', '.'])

		# Put the example tornado files in there.
		shutil.copy(os.path.join(sample_dir, 'app.py'), self.repo)
		shutil.copy(os.path.join(sample_dir, 'manifest.yml'), self.repo)

		# Check them in.
		self._run_git_command(['git', 'add', '.'])
		self._run_git_command(['git', 'commit', '-m', 'Initial checkin.'])

		# Create a branch, update one of the files, then check that in.
		self._run_git_command(['git', 'branch', 'test'])
		self._run_git_command(['git', 'checkout', 'test'])

		open(os.path.join(self.repo, 'app.py'), 'a').write("\n# Test update\n");

		self._run_git_command(['git', 'add', '.'])
		self._run_git_command(['git', 'commit', '-m', 'Updated in branch.'])

		# Go back to master.
		self._run_git_command(['git', 'checkout', 'master'])

		# Register the plugin.
		self.registry.register(
			'paasmaker.scm.git',
			'paasmaker.pacemaker.scm.git.GitSCM',
			{},
			'Git SCM'
		)

	def tearDown(self):
		# Delete the repo.
		shutil.rmtree(self.repo)

		super(GitSCMTest, self).tearDown()

	def test_extract_manifest(self):
		# Now unpack it using the plugin.
		logger = self.configuration.get_job_logger('testscmgit')
		plugin = self.registry.instantiate(
			'paasmaker.scm.git',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{
				'location': self.repo
			},
			logger
		)

		# Extract a manifest file.
		plugin.extract_manifest('manifest.yml', self.stop, self.stop)
		result = self.wait()

		# Check that the manifest was returned.
		self.assertIn("format: 1", result, "Missing manifest contents.")

		# Try to extract an invalid manifest path.
		plugin.extract_manifest('manifest_noexist.yml', self.stop, self.stop)
		result = self.wait()
		self.assertIn("Unable to locate", result, "Missing error message.")

	def test_working_copy(self):
		logger = self.configuration.get_job_logger('testscmgit')
		plugin = self.registry.instantiate(
			'paasmaker.scm.git',
			paasmaker.util.plugin.MODE.SCM_EXPORT,
			{
				'location': self.repo
			},
			logger
		)

		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not clone properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertFalse(os.path.exists(os.path.join(self.path, '.git')), "Output directory still has git metadata.")

		# Change a app.py in the source repo, then run it again.
		# This time it should pull the changes, and apply them.
		open(os.path.join(self.repo, 'app.py'), 'a').write("\n# Test update - in master\n");
		self._run_git_command(['git', 'add', '.'])
		self._run_git_command(['git', 'commit', '-m', 'Updated for pull.'])

		# And make sure we can now pull.
		plugin.create_working_copy(self.success_callback, self.failure_callback)

		self.wait()

		self.assertTrue(self.success, "Did not clone properly.")
		self.assertTrue(os.path.exists(os.path.join(self.path, 'app.py')), "app.py does not exist.")
		self.assertFalse(os.path.exists(os.path.join(self.path, '.git')), "Output directory still has git metadata.")
		app_contents = open(os.path.join(self.path, 'app.py'), 'r').read()
		self.assertIn("Test update - in master", app_contents, "Local checkout was not updated.")

		# TODO: Test the error paths in this file, as there are so many of them.