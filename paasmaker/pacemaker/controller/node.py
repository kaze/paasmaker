import unittest
import paasmaker
import uuid
import logging
import colander
import json
from paasmaker.common.controller import BaseController, BaseControllerTest

import tornado
import tornado.testing

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

class NodeRegisterSchema(colander.MappingSchema):
	name = colander.SchemaNode(colander.String(),
		title="Node Name",
		description="A nice name for the node.")
	route = colander.SchemaNode(colander.String(),
		title="Route to this node",
		description="The route to access this node for future. Can be a DNS name of IP address.")
	apiport = colander.SchemaNode(colander.String(),
		title="HTTP API port",
		description="The HTTP port to use to interact with this node.")
	tags = colander.SchemaNode(colander.Mapping(unknown='preserve'),
		title="User tags",
		description="A generic set of tags or information stored for the node. Can be used to write custom placement filters, or find nodes.")

class NodeUpdateSchema(NodeRegisterSchema):
	uuid = colander.SchemaNode(colander.String(),
		title="UUID",
		description="The existing UUID of the node.")

class NodeController(BaseController):
	auth_methods = [BaseController.NODE]

	def get(self):
		self.render("api/apionly.html")

	@tornado.web.asynchronous
	@tornado.gen.engine
	def post(self, action):
		if action == 'register':
			self.validate_data(NodeRegisterSchema())
		elif action == 'update':
			self.validate_data(NodeUpdateSchema())

		do_connectivity_check = False
		if action == 'register':
			# Create a UUID for this node.
			new_uuid = str(uuid.uuid4())

			# Look for nodes with the same route/API port.
			duplicate_node = self.db().query(paasmaker.model.Node) \
				.filter(paasmaker.model.Node.route==self.param('route')) \
				.filter(paasmaker.model.Node.apiport==self.param('apiport')).first()

			if duplicate_node:
				self.add_error("Node appears to already be registered - name %s, UUID %s." % (duplicate_node.name, duplicate_node.uuid))
			else:
				node = paasmaker.model.Node(self.param('name'), self.param('route'), self.param('apiport'), new_uuid, 'ACTIVE')
				logger.debug("New node %s(%s:%d), assigned UUID %s. Checking connectivity...", node.name, node.route, node.apiport, new_uuid)
				do_connectivity_check = True

		if action == 'update':
			# Find the node.
			node = self.db().query(paasmaker.model.Node) \
				.filter(paasmaker.model.Node.uuid==self.param('uuid')).first()

			if not node:
				self.add_error("Can't find your node record. Please register instead.")
			else:
				# Update the node.
				node.name = self.param('name')
				node.route = self.param('route')
				node.apiport = self.param('apiport')
				node.state = 'ACTIVE'
				do_connectivity_check = True

		# If we're doing a connectivity check, also update the other attributes for the node.
		if do_connectivity_check:
			tags = self.param('tags')
			node.heart = tags['roles']['heart']
			node.pacemaker = tags['roles']['pacemaker']
			node.router = tags['roles']['router']

			node.tags = json.dumps(tags, cls=paasmaker.util.jsonencoder.JsonEncoder)

		if do_connectivity_check:
			# Attempt to connect to the node...
			request = paasmaker.common.api.information.InformationAPIRequest(self.configuration, self.io_loop)
			request.set_target(node)
			# TODO: Make the timeout configurable.
			response = yield tornado.gen.Task(request.send, connect_timeout=1.0)
			if response.success:
				# Success! Save the node.
				session = self.db()
				session.add(node)
				session.commit()

				# Send back the appropriate data.
				self.add_data('node', node)
				logger.info("Successfully %s node %s(%s:%d) UUID %s", action, node.name, node.route, node.apiport, node.uuid)
			else:
				self.add_errors(response.errors)
				logger.error("Failed to connect to node %s(%s:%d) UUID %s", node.name, node.route, node.apiport, node.uuid)
				for error in self.errors:
					logger.error(error)

		# Return the response.
		self.render("api/apionly.html")
		self.finish()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/node/(register|update)", NodeController, configuration))
		return routes

class NodeControllerTest(BaseControllerTest):
	config_modules = ['pacemaker', 'heart']

	def get_app(self):
		self.late_init_configuration()
		routes = NodeController.get_routes({'configuration': self.configuration, 'io_loop': self.io_loop})
		routes.extend(paasmaker.common.controller.InformationController.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_register(self):
		# Register the node.
		request = NodeRegisterAPIRequestLocalHost(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")

		self.assertEquals(self.configuration.get_node_uuid(), response.data['node']['uuid'], "Returned UUID doesn't match our UUID.")

		first_id = response.data['node']['id']

		# Register again. This should fail, as it detects the same route/port combination.
		request = NodeRegisterAPIRequestLocalHost(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)

		# Now update our node.
		request = NodeUpdateAPIRequestLocalHost(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('node'), "Missing node object in return data.")
		self.assertTrue(response.data['node'].has_key('id'), "Missing ID in return data.")
		self.assertTrue(response.data['node'].has_key('uuid'), "Missing UUID in return data.")
		self.assertEquals(first_id, response.data['node']['id'], "Updated ID is different to original.")

	def test_fail_connect_port(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailPort(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 1, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

	def test_fail_update_no_exist(self):
		request = NodeUpdateAPIRequestFailUUID(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 1, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

	def test_fail_connect_host(self):
		# Test when it can't connect.
		request = NodeRegisterAPIRequestFailHost(self.configuration, self.io_loop)
		request.send(self.stop)
		response = self.wait()

		self.failIf(response.success)
		self.assertEquals(len(response.errors), 1, "There were no errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")

class NodeRegisterAPIRequestLocalHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def build_payload(self):
		data = super(NodeRegisterAPIRequestLocalHost, self).build_payload()
		data['route'] = 'localhost'
		return data

class NodeUpdateAPIRequestLocalHost(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back localhost as the route - on some machines,
	the local path detection causes the unit tests to fail.
	"""
	def build_payload(self):
		data = super(NodeUpdateAPIRequestLocalHost, self).build_payload()
		data['route'] = 'localhost'
		return data

class NodeRegisterAPIRequestFailPort(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty HTTP port, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		data = super(NodeRegisterAPIRequestFailPort, self).build_payload()
		data['apiport'] += 1000
		return data

class NodeRegisterAPIRequestFailHost(paasmaker.common.api.NodeRegisterAPIRequest):
	"""
	Stub class to send back a faulty route, to stop it from accessing the remote end.
	"""
	def build_payload(self):
		data = super(NodeRegisterAPIRequestFailHost, self).build_payload()
		data['route'] = 'noexist.paasmaker.com'
		return data

class NodeUpdateAPIRequestFailUUID(paasmaker.common.api.NodeUpdateAPIRequest):
	"""
	Stub class to send back a faulty UUID.
	"""
	def build_payload(self):
		data = super(NodeUpdateAPIRequestFailUUID, self).build_payload()
		data['uuid'] = 'no node to see here'
		return data