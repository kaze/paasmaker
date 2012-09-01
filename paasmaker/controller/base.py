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

	def prepare(self):
		self._set_format(self.get_argument('format', 'html'))

	def add_data(self, key, name):
		self.data[key] = name

	def add_data_template(self, key, name):
		self.template[key] = name

	def add_error(self, error):
		self.errors.append(error)

	def add_warning(self, warning):
		self.warnings.append(warning)

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

class BaseWebsocketHandler(tornado.websocket.WebSocketHandler):
	"""
	Base class for WebsocketHandlers.
	"""
	def initialize(self, configuration):
		self.configuration = configuration

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

