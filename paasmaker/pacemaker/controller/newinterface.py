
import paasmaker
import tornado
from paasmaker.common.controller import BaseController

class NewInterfaceController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.render("new.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/new", NewInterfaceController, configuration))
		return routes

class NewInterfaceQUnitTestController(BaseController):
	AUTH_METHODS = [BaseController.USER]

	def get(self):
		self.render("qunit.html")

	@staticmethod
	def get_routes(configuration):
		routes = []
		routes.append((r"/qunit", NewInterfaceQUnitTestController, configuration))
		return routes