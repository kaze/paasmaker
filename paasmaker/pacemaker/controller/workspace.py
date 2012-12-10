import unittest
import uuid
import logging
import json

import paasmaker
from paasmaker.common.controller import BaseController, BaseControllerTest
from paasmaker.common.core import constants

import colander
import tornado
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class WorkspaceSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Workspace Name",
		description="The name of this workspace.",
		validator=colander.Length(min=2))
	# TODO: Put proper validation on this.
	stub = colander.SchemaNode(colander.String(),
		title="Workspace stub",
		description="A short, URL friendly name for the workspace.")
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="Workspace Tags",
		description="A set of tags for this workspace.",
		missing={},
		default={})

class WorkspaceEditController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def _get_workspace(self, workspace_id=None):
		workspace = None
		if workspace_id:
			# Find and load the user.
			workspace = self.db().query(paasmaker.model.Workspace).get(int(workspace_id))
			if not workspace:
				raise HTTPError(404, "No such workspace.")

			self.add_data('workspace', workspace)

		return workspace

	def _default_workspace(self):
		workspace = paasmaker.model.Workspace()
		workspace.name = ''
		return workspace

	def get(self, workspace_id=None):
		workspace = self._get_workspace(workspace_id)
		self.require_permission(constants.PERMISSION.WORKSPACE_EDIT, workspace=workspace)
		if not workspace:
			workspace = self._default_workspace()
		self.add_data('workspace', workspace)

		self.render("workspace/edit.html")

	def post(self, workspace_id=None):
		workspace = self._get_workspace(workspace_id)
		self.require_permission(constants.PERMISSION.WORKSPACE_EDIT, workspace=workspace)

		valid_data = self.validate_data(WorkspaceSchema())

		if not workspace:
			workspace = self._default_workspace()

		workspace.name = self.params['name']
		workspace.tags = self.params['tags']
		workspace.stub = self.params['stub']

		if valid_data:
			session = self.db()
			session.add(workspace)
			session.commit()
			session.refresh(workspace)

			self.add_data('workspace', workspace)

			self.redirect('/workspace/list')
		else:
			self.add_data('workspace', workspace)
			self.render("workspace/edit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/create", WorkspaceEditController, configuration))
		routes.append((r"/workspace/(\d+)", WorkspaceEditController, configuration))
		return routes

class WorkspaceListController(BaseController):
	AUTH_METHODS = [BaseController.SUPER, BaseController.USER]

	def get(self):
		self.require_permission(constants.PERMISSION.WORKSPACE_LIST)
		# TODO: Filter to your workspaces.
		workspaces = self.db().query(
			paasmaker.model.Workspace
		).filter(
			paasmaker.model.Workspace.deleted == None
		)
		self._paginate('workspaces', workspaces)
		self.render("workspace/list.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/workspace/list", WorkspaceListController, configuration))
		return routes

class WorkspaceEditControllerTest(BaseControllerTest):
	config_modules = ['pacemaker']

	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = WorkspaceEditController.get_routes({'configuration': self.configuration})
		routes.extend(WorkspaceListController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_create(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('workspace'), "Missing workspace object in return data.")
		self.assertTrue(response.data['workspace'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['workspace'].has_key('name'), "Missing name in return data.")

	def test_create_fail(self):
		# Send through some bogus data.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('a')
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('name'), "Missing error on name attribute.")

	def test_edit(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the workspace.
		request.set_workspace_name('Test Altered workspace')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(response.data['workspace']['name'], 'Test Altered workspace', 'Name was not updated.')
		# Load up the workspace separately and confirm.
		workspace = self.configuration.get_database_session().query(paasmaker.model.Workspace).get(workspace_id)
		self.assertEquals(workspace.name, 'Test Altered workspace', 'Name was not updated.')

	def test_edit_fail(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		workspace_id = response.data['workspace']['id']

		# Set up the request.
		request = paasmaker.common.api.workspace.WorkspaceEditAPIRequest(self.configuration)
		request.set_superkey_auth()
		# This loads the workspace data from the server.
		request.load(workspace_id, self.stop, self.stop)
		load_response = self.wait()

		# Now attempt to change the workspace.
		request.set_workspace_name('a')

		# Send it along!
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		input_errors = response.data['input_errors']
		self.assertTrue(input_errors.has_key('name'), "Missing error on name attribute.")

	def test_list(self):
		# Create the workspace.
		request = paasmaker.common.api.workspace.WorkspaceCreateAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.set_workspace_name('Test workspace')
		request.set_workspace_stub('test')
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)

		request = paasmaker.common.api.workspace.WorkspaceListAPIRequest(self.configuration)
		request.set_superkey_auth()
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertTrue(response.data.has_key('workspaces'), "Missing workspaces list.")
		self.assertEquals(len(response.data['workspaces']), 1, "Not enough workspaces returned.")
		self.assertEquals(response.data['workspaces'][0]['name'], 'Test workspace', "Returned workspace is not as expected.")
