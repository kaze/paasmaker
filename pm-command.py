#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import argparse

import sys
import json

# Internal imports.
import paasmaker

# Logging setup.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# TODO: Write tests for all the actions in this file. Integration tests might cover this off
# though? But need to make sure we have appropriate coverage.

# TODO: When an error occurs, exit.

class RootAction(object):
	def options(self, parser):
		# Define your options here.
		pass

	def process(self, args):
		self.exit()

	def describe(self):
		raise NotImplementedError("Not implemented.")

	def prettyprint(self, data):
		print json.dumps(data, indent=4, sort_keys=True)

	def exit(self, code):
		tornado.ioloop.IOLoop.instance().stop()
		sys.exit(code)

	def point_and_auth(self, args, apirequest):
		scheme = 'http'
		if args.ssl:
			scheme = 'https'
		host = "%s://%s:%d" % (scheme, args.remote, args.port)
		apirequest.set_target(host)
		if args.apikey:
			apirequest.set_apikey_auth(args.apikey)
		elif args.superkey:
			apirequest.set_superkey_auth(args.superkey)

	def generic_request_failed(self, message, exception=None):
		logging.error(message)
		if exception:
			logging.error(exception)
		self.exit(1)

	def generic_api_response_check_failed(self, response):
		if not response.success:
			self.generic_api_response(response)

	def generic_api_response(self, response):
		if response.success:
			logging.info("Successfully executed request.")
			# TODO: Handle warnings.
			self.prettyprint(response.data)
			sys.exit(0)
		else:
			logging.error("Request failed.")
			for error in response.errors:
				logging.error(error)
			# TODO: Print errors in JSON format.
			self.prettyprint(response.data)
			self.exit(1)

class UserCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("login", help="User login name")
		parser.add_argument("email", help="Email address")
		parser.add_argument("name", help="User name")
		parser.add_argument("password", help="Password")

	def describe(self):
		return "Create a user."

	def process(self, args):
		request = paasmaker.common.api.user.UserCreateAPIRequest(None)
		request.set_user_params(args.name, args.login, args.email, True)
		request.set_user_password(args.password)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class UserEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("user_id", help="User ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the user.")
		parser.add_argument("--email", type=str, default=None, help="The email of the user.")
		parser.add_argument("--login", type=str, default=None, help="The login of the user.")
		parser.add_argument("--password", type=str, default=None, help="The password of the user.")

	def describe(self):
		return "Edit a user."

	def process(self, args):
		def user_loaded(roledata):
			if args.name:
				request.set_user_name(args.name)
			if args.login:
				request.set_user_login(args.login)
			if args.email:
				request.set_user_email(args.email)
			if args.password:
				request.set_user_password(args.password)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.user.UserEditAPIRequest(None)
		self.point_and_auth(args, request)
		request.load(int(args.user_id), user_loaded, self.generic_request_failed)

class UserGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("user_id", help="User ID to fetch")

	def describe(self):
		return "Get a user record."

	def process(self, args):
		request = paasmaker.common.api.user.UserGetAPIRequest(None)
		request.set_user(int(args.user_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class UserListAction(RootAction):
	def describe(self):
		return "List users."

	def process(self, args):
		request = paasmaker.common.api.user.UserListAPIRequest(None)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class UserEnableAction(RootAction):
	ENABLE = True

	def options(self, parser):
		parser.add_argument("user_id", help="User ID to change.")

	def describe(self):
		if self.ENABLE:
			return "Enable a user."
		else:
			return "Disable a user."

	def process(self, args):
		def user_loaded(response):
			self.generic_api_response_check_failed(response)
			request.set_user_enabled(self.ENABLE)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.user.UserEditAPIRequest(None)
		self.point_and_auth(args, request)
		request.load(int(args.user_id), user_loaded)

class UserDisableAction(UserEnableAction):
	ENABLE = False

class RoleCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("name", help="Role name")
		parser.add_argument("permissions", help="Comma seperated list of permissions")

	def describe(self):
		return "Create a role."

	def process(self, args):
		permissions = args.permissions.replace(" ", "").split(",")

		request = paasmaker.common.api.role.RoleCreateAPIRequest(None)
		request.set_role_params(args.name, permissions)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class RoleEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", help="Role ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the role.")
		parser.add_argument("--permissions", type=str, default=None, help="The permissions assigned to the role. Replaces all the permissions with the set provided.")

	def describe(self):
		return "Edit a role."

	def process(self, args):
		def role_loaded(roledata):
			if args.name:
				request.set_role_name(args.name)
			if args.permissions:
				permissions = args.permissions.replace(" ", "").split(",")
				request.set_role_permissions(permissions)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.role.RoleEditAPIRequest(None)
		self.point_and_auth(args, request)
		request.load(int(args.role_id), role_loaded, self.generic_request_failed)

class RoleGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", help="Role ID to fetch")

	def describe(self):
		return "Get a role record."

	def process(self, args):
		request = paasmaker.common.api.role.RoleGetAPIRequest(None)
		request.set_role(int(args.role_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class RoleListAction(RootAction):
	def describe(self):
		return "List roles."

	def process(self, args):
		request = paasmaker.common.api.role.RoleListAPIRequest(None)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class RoleAllocationListAction(RootAction):
	def describe(self):
		return "List role allocations."

	def process(self, args):
		request = paasmaker.common.api.role.RoleAllocationListAPIRequest(None)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class RoleAllocationAction(RootAction):
	def options(self, parser):
		parser.add_argument("role_id", type=int, help="Role ID to assign")
		parser.add_argument("user_id", type=int, help="User ID to assign")
		parser.add_argument("--workspace_id", type=int, help="Workspace ID to assign (optional)", default=None)

	def describe(self):
		return "Allocate a role to a user and workspace."

	def process(self, args):
		request = paasmaker.common.api.role.RoleAllocationAPIRequest(None)
		workspace_id = None
		if args.workspace_id:
			workspace_id = int(args.workspace_id)
		request.set_allocation_params(int(args.user_id), int(args.role_id), workspace_id)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class RoleUnAllocateAction(RootAction):
	def options(self, parser):
		parser.add_argument("allocation_id", help="Allocation to remove.")

	def describe(self):
		return "Remove a role allocation."

	def process(self, args):
		request = paasmaker.common.api.role.RoleUnAllocationAPIRequest(None)
		request.set_role(int(args.allocation_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class WorkspaceCreateAction(RootAction):
	def options(self, parser):
		parser.add_argument("name", help="Workspace name")
		parser.add_argument("stub", help="Workspace stub")
		parser.add_argument("tags", help="JSON formatted tags for this workspace.", default="{}")

	def describe(self):
		return "Create a workspace."

	def process(self, args):
		tags = json.loads(args.tags)

		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(None)
		request.set_workspace_name(args.name)
		request.set_workspace_stub(args.stub)
		request.set_workspace_tags(tags)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class WorkspaceEditAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to edit")
		parser.add_argument("--name", type=str, default=None, help="The name of the workspace.")
		parser.add_argument("--stub", type=str, default=None, help="The stub of the workspace.")
		parser.add_argument("--tags", type=str, default=None, help="JSON formatted tags for this workspace.")

	def describe(self):
		return "Edit a workspace."

	def process(self, args):
		def workspace_loaded(roledata):
			if args.name:
				request.set_workspace_name(args.name)
			if args.tags:
				tags = json.loads(args.tags)
				request.set_workspace_tags(tags)
			if args.stub:
				request.set_workspace_stub(args.stub)
			request.send(self.generic_api_response)

		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(None)
		self.point_and_auth(args, request)
		request.load(int(args.workspace_id), workspace_loaded, self.generic_request_failed)

class WorkspaceGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to fetch")

	def describe(self):
		return "Get a workspace record."

	def process(self, args):
		request = paasmaker.common.api.workspace.WorkspaceGetAPIRequest(None)
		request.set_workspace(int(args.workspace_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class WorkspaceListAction(RootAction):
	def describe(self):
		return "List workspaces."

	def process(self, args):
		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(None)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class NodeListAction(RootAction):
	def describe(self):
		return "List nodes."

	def process(self, args):
		request = paasmaker.common.api.nodelist.NodeListAPIRequest(None)
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class FileUploadAction(RootAction):
	def options(self, parser):
		parser.add_argument("filename", help="The filename to upload.")

	def describe(self):
		return "Upload a file to the server. NOTE: Must use user authentication."

	def _progress(self, position, total):
		percent = (float(position) / float(total)) * 100;
		logger.info("%d bytes of %d uploaded (%.2f%%).", position, total, percent)

	def _finished(self, data):
		self.prettyprint(data['data'])
		self.exit(0)

	def _error(self, message):
		logger.error("Failed to upload: %s", message)
		self.prettyprint(data)
		self.exit(1)

	def process(self, args):
		# TODO: This times out on large files, waiting for the server to assemble them.
		if not args.apikey:
			logger.error("You must use an API key to authenticate to upload files.")
			self.exit(1)
		else:
			request = paasmaker.common.api.upload.UploadFileAPIRequest(None)
			self.point_and_auth(args, request)
			request.send_file(
				args.filename,
				self._progress,
				self._finished,
				self._error
			)

class ApplicationGetAction(RootAction):
	def options(self, parser):
		parser.add_argument("application_id", help="Application ID to fetch")

	def describe(self):
		return "Get an application record."

	def process(self, args):
		request = paasmaker.common.api.application.ApplicationGetAPIRequest(None)
		request.set_application(int(args.application_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class ApplicationListAction(RootAction):
	def options(self, parser):
		parser.add_argument("workspace_id", help="Workspace ID to list")

	def describe(self):
		return "List applications in the given workspace."

	def process(self, args):
		request = paasmaker.common.api.application.ApplicationListAPIRequest(None)
		request.set_workspace(int(args.workspace_id))
		self.point_and_auth(args, request)
		request.send(self.generic_api_response)

class HelpAction(RootAction):
	def options(self, parser):
		pass

	def process(self, args):
		help_keys = ACTION_MAP.keys()
		help_keys.sort()
		for key in help_keys:
			logging.info("%s: %s", key, ACTION_MAP[key].describe())

		self.exit(0)

	def describe(self):
		return "Show a list of actions."

# Peek ahead at the command line options for the main action.
if len(sys.argv) == 1:
	# Nothing supplied.
	print "No module supplied. Usage: %s action" % sys.argv[0]
	print "Try %s help" % sys.argv[0]
	sys.exit(1)

action = sys.argv[1]

ACTION_MAP = {
	'user-create': UserCreateAction(),
	'user-edit': UserEditAction(),
	'user-get': UserGetAction(),
	'user-list': UserListAction(),
	'user-enable': UserEnableAction(),
	'user-disable': UserDisableAction(),
	'role-create': RoleCreateAction(),
	'role-edit': RoleEditAction(),
	'role-get': RoleGetAction(),
	'role-list': RoleListAction(),
	'workspace-create': WorkspaceCreateAction(),
	'workspace-edit': WorkspaceEditAction(),
	'workspace-get': WorkspaceGetAction(),
	'workspace-list': WorkspaceListAction(),
	'node-list': NodeListAction(),
	'role-allocation-list': RoleAllocationListAction(),
	'role-allocate': RoleAllocationAction(),
	'role-unallocate': RoleUnAllocateAction(),
	'file-upload': FileUploadAction(),
	'application-get': ApplicationGetAction(),
	'application-list': ApplicationListAction(),
	'help': HelpAction()
}

# If there is no action...
if not ACTION_MAP.has_key(action):
	print "No such action %s. Try %s help" % (action, sys.argv[0])
	sys.exit(1)

# Set up our parser.
parser = argparse.ArgumentParser()
parser.add_argument('action', help="The action to perform.")

# Set up common command line options.
parser.add_argument("-r", "--remote", default="localhost", help="The pacemaker host.")
parser.add_argument("-p", "--port", type=int, default=42500, help="The pacemaker port.")
parser.add_argument("-k", "--apikey", help="User API key to authenticate with.")
parser.add_argument("--ssl", default=False, help="Use SSL to connect to the node.", action="store_true")
parser.add_argument("--superkey", default="", help="Super key to authenticate with.")
parser.add_argument("--loglevel", default="INFO", help="Log level, one of DEBUG|INFO|WARNING|ERROR|CRITICAL.")

# Now get our action to set up it's options.
ACTION_MAP[action].options(parser)

# Parse all the arguments.
args = parser.parse_args()

# Reset the log level.
logging.debug("Resetting log level to %s.", args.loglevel)
logger = logging.getLogger()
logger.setLevel(getattr(logging, args.loglevel))

logger.debug("Parsed command line arguments: %s", str(args))

# Make sure we have an auth source.
if not args.superkey and not args.apikey:
	logger.error("No API or node key passed.")
	sys.exit(1)

# Now we wait for the IO loop to start before starting.
def on_start():
	ACTION_MAP[action].process(args)

# Commence the application.
if __name__ == "__main__":
	# Start the loop.
	try:
		tornado.ioloop.IOLoop.instance().add_callback(on_start)
		tornado.ioloop.IOLoop.instance().start()
		logging.debug("Exiting.")
	except Exception, ex:
		# Catch all, to catch things thrown in the callbacks.
		logging.error(ex)
		tornado.ioloop.IOLoop.instance().stop()
