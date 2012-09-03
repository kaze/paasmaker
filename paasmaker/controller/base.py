#!/usr/bin/env python

import tornado.web
import tornado.websocket
import logging
import paasmaker
import tornado.testing
import warnings
import os
import json
import time

import colander

# Types of API requests.
# 1. Node->Node. (ie, nodes talking to each other)
# 2. User->Pacemaker (cookie auth) (ie, AJAX browser callback)
# 3. User->Pacemaker (token auth) (ie, command line tool or other API request)

# Structure of API requests.
# auth: { method: 'node|cookie|token', value: 'token|cookie' }
# data: { ... keys ... }

class APIAuthRequestSchema(colander.MappingSchema):
	method = colander.SchemaNode(colander.String(),
		title="Method of authentication",
		description="One of node, cookie, or token")
	value = colander.SchemaNode(colander.String(),
		title="Authentication value",
		description="The authentication value")

class APIRequestSchema(colander.MappingSchema):
	auth = APIAuthRequestSchema()
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class BaseController(tornado.web.RequestHandler):
	"""
	Base class for all controllers in the system.
	"""
	def initialize(self, configuration):
		self.configuration = configuration
		self.data = {}
		self.template = {}
		self.errors = []
		self.warnings = []
		self.format = 'html'
		self.root_data = {}
		self.session = None
		self.auth = {}

	def prepare(self):
		self._set_format(self.get_argument('format', 'html'))

		# If the post body is JSON, parse it and put it into the arguments.
		# TODO: This JSON detection is lightweight, but there might be corner
		# cases in it too...
		if self.request.method == 'POST' and self.request.body[0] == '{' and self.request.body[-1] == '}':
			parsed = json.loads(self.request.body)
			schema = APIRequestSchema()
			try:
				result = schema.deserialize(parsed)
			except colander.Invalid, ex:
				self.send_error(400, exc_info=ex)
				return
			self.auth = result['auth']
			self.request.arguments.update(result['data'])

	def add_data(self, key, name):
		self.data[key] = name

	def add_data_template(self, key, name):
		self.template[key] = name

	def add_error(self, error):
		self.errors.append(error)

	def add_warning(self, warning):
		self.warnings.append(warning)

	def db(self):
		if self.session:
			return self.session
		self.session = self.configuration.get_database_session()
		return self.session

	def _set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format
		
	def render(self, template, **kwargs):
		# Prepare our variables.
		if self.format == 'json':
			variables = {}
			variables.update(self.root_data)
			variables['data'] = self.data
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			self.set_header('Content-Type', 'application/json')
			self.write(json.dumps(variables, cls=paasmaker.util.jsonencoder.JsonEncoder))
		elif self.format == 'html':
			variables = self.data
			variables.update(self.root_data)
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			variables.update(self.template)
			variables.update(kwargs)
			super(BaseController, self).render(template, **variables)

	def write_error(self, status_code, **kwargs):
		# Reset the data queued up until now.
		self.data = {}
		self.root_data['error_code'] = status_code
		if kwargs.has_key('exc_info'):
			self.add_error('Exception: ' + str(kwargs['exc_info'][0]) + ': ' + str(kwargs['exc_info'][1]))
		self.render('error/error.html')

	def on_finish(self):
		self.application.log_request(self)

# A schema for websocket incoming messages, to keep them consistent.
class WebsocketMessageSchema(colander.MappingSchema):
	request = colander.SchemaNode(colander.String(),
		title="Request",
		description="What is intended from this request")
	sequence = colander.SchemaNode(colander.Integer(),
		title="Sequence",
		description="The sequence number for this request. Errors are returned matching this sequence, so you can tell which request they originated from. Optional",
		default=0,
		missing=0)
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))
	auth = APIAuthRequestSchema()

class BaseWebsocketHandler(tornado.websocket.WebSocketHandler):
	"""
	Base class for WebsocketHandlers.
	"""
	def initialize(self, configuration):
		self.configuration = configuration

	def parse_message(self, message):
		parsed = json.loads(message)
		schema = WebsocketMessageSchema()
		try:
			result = schema.deserialize(parsed)

			# Validate their authentication details.
			# Have to be authenticated for anything to work.
			# TODO: Implement!
		except colander.Invalid, ex:
			if not parsed.has_key('sequence'):
				parsed['sequence'] = -1
			self.send_error(str(ex), parsed)
			return None

		return result

	def validate_data(self, message, schema):
		try:
			result = schema.deserialize(message['data'])
		except colander.Invalid, ex:
			self.send_error(str(ex), message)
			return None

		return result

	def send_error(self, error, message):
		self.write_message(self.encode_message(self.make_error(error, message)))

	def send_success(self, typ, data):
		self.write_message(self.encode_message(self.make_success(typ, data)))

	def make_error(self, error, message):
		message = {
			'type': 'error',
			'data': { 'error': error, 'sequence': message['sequence'] }
		}
		return message

	def make_success(self, typ, data):
		message = {
			'type': typ,
			'data': data
		}
		return message

	def encode_message(self, message):
		return json.dumps(message, cls=paasmaker.util.jsonencoder.JsonEncoder)

class BaseControllerTest(tornado.testing.AsyncHTTPTestCase):
	def setUp(self):
		self.configuration = paasmaker.configuration.ConfigurationStub()
		super(BaseControllerTest, self).setUp()
	def tearDown(self):
		self.configuration.cleanup()
		super(BaseControllerTest, self).tearDown()

	def short_wait_hack(self):
		self.io_loop.add_timeout(time.time() + 0.1, self.stop)

