#!/usr/bin/env python

from base import BaseController
from base import BaseControllerTest
from base import BaseWebsocketHandler
import unittest
import json

import tornado
import tornado.testing
from ws4py.client.tornadoclient import TornadoWebSocketClient

class ExampleController(BaseController):
	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example", ExampleController, configuration))
		return routes

class ExampleFailController(BaseController):
	def get(self):
		self.add_data("test", "Hello")
		self.add_data_template("template", "Template")
		raise Exception('Oh Hai!')
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-fail", ExampleFailController, configuration))
		return routes

class ExamplePostController(BaseController):
	def post(self):
		self.add_data("test", "Hello")
		self.add_data("output", self.request.arguments["more"])
		self.add_data_template("template", "Template")
		self.render("example/index.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-post", ExamplePostController, configuration))
		return routes

class ExampleWebsocketHandler(BaseWebsocketHandler):
	events = []

	def open(self):
		self.events.append('Opened')

	def on_message(self, message):
		# CAUTION: message is not a string! You will need to explicitly str() it
		# if you want to JSON decode it.
		self.write_message(u"You said: " + message)
		self.events.append(message)

	def on_close(self):
		self.events.append('Closed')

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/example-websocket", ExampleWebsocketHandler, configuration))
		return routes

class ExampleWebsocketHandlerTestClient(TornadoWebSocketClient):
	events = []
	def opened(self):
		self.events.append('Opened')
	def closed(self, code, reason):
		self.events.append('Closed: %d %s' % (code, reason))
	def received_message(self, m):
		self.events.append('Got message: %s' % m)

class ExampleControllerTest(BaseControllerTest):
	def get_app(self):
		routes = ExampleController.get_routes({'configuration': self.configuration})
		routes.extend(ExampleFailController.get_routes({'configuration': self.configuration}))
		routes.extend(ExamplePostController.get_routes({'configuration': self.configuration}))
		routes.extend(ExampleWebsocketHandler.get_routes({'configuration': self.configuration}))
		application = tornado.web.Application(routes, **self.configuration.get_torando_configuration())
		return application

	def test_example(self):
		self.http_client.fetch(self.get_url('/example'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertIn("Hello, ", response.body)

	def test_example_json(self):
		self.http_client.fetch(self.get_url('/example?format=json'), self.stop)
		response = self.wait()
		self.failIf(response.error)
		self.assertNotIn("Template", response.body)
		self.assertIn("Hello", response.body)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), 'Missing root data key.')
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertTrue(decoded['data'].has_key('test'), 'Missing test data key.')
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')

	def test_example_fail(self):
		self.http_client.fetch(self.get_url('/example-fail?format=json'), self.stop)
		response = self.wait()
		self.failIf(not response.error)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), 'Missing root data key.')
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(len(decoded['errors']) > 0, 'No errors reported.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertFalse(decoded['data'].has_key('test'), 'Missing test data key.')
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')

	def test_post_json(self):
		more = 2
		body = json.dumps({'test': 'bar', 'more': more})
		request = tornado.httpclient.HTTPRequest(
			"http://localhost:%d/example-post?format=json" % self.get_http_port(),
			method="POST",
			body=body)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
		response = self.wait()

		self.failIf(response.error)
		decoded = json.loads(response.body)
		self.assertTrue(decoded.has_key('data'), "Missing data key.")
		self.assertTrue(decoded.has_key('errors'), 'Missing root errors key.')
		self.assertTrue(len(decoded['errors']) == 0, 'Errors were reported.')
		self.assertTrue(decoded.has_key('warnings'), 'Missing root warnings key.')
		self.assertTrue(decoded['data'].has_key('test'), "Missing test key.")
		self.assertFalse(decoded['data'].has_key('template'), 'Includes template data key.')
		self.assertEquals(decoded['data']['output'], more, 'Value was not retained.')

	def test_example_websocket(self):
		client = ExampleWebsocketHandlerTestClient("ws://localhost:%d/example-websocket" % self.get_http_port(), io_loop=self.io_loop)
		client.connect()
		self.short_wait_hack()
		self.wait() # Waiting for everything to settle.

		# Send it a short message.
		client.send('test')
		self.short_wait_hack()
		self.wait() # Wait for processing of that message.

		client.close()
		self.short_wait_hack()
		self.wait() # Wait for closing.

		self.assertEquals(len(client.events), 3, "Missing events.")
		

if __name__ == '__main__':
	tornado.testing.main()
