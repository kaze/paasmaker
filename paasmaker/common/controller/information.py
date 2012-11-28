from base import BaseController
from base import BaseControllerTest
import unittest
import paasmaker

import tornado
import tornado.testing

class InformationController(BaseController):
	AUTH_METHODS = [BaseController.NODE, BaseController.USER, BaseController.SUPER]

	def get(self):
		self.add_data('is_heart', self.configuration.is_heart())
		self.add_data('is_pacemaker', self.configuration.is_pacemaker())
		self.render("api/apionly.html")

	def post(self):
		return self.get()

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/information", InformationController, configuration))
		return routes

class InformationControllerTest(BaseControllerTest):
	def get_app(self):
		self.late_init_configuration(self.io_loop)
		routes = InformationController.get_routes({'configuration': self.configuration})
		application = tornado.web.Application(routes, **self.configuration.get_tornado_configuration())
		return application

	def test_information(self):
		request = paasmaker.common.api.information.InformationAPIRequest(self.configuration)
		request.send(self.stop)
		response = self.wait()

		self.failIf(not response.success)
		self.assertEquals(len(response.errors), 0, "There were errors.")
		self.assertEquals(len(response.warnings), 0, "There were warnings.")
		self.assertTrue(response.data.has_key('is_heart'))
		self.assertTrue(response.data.has_key('is_pacemaker'))
