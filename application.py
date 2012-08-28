#!/usr/bin/env python

# External library imports.
import tornado.ioloop
import tornado.web

# Internal imports.
import paasmaker

# Logging setup.
# TODO: Allow this to be controlled by command line / configuration.
import logging
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)

# Load configuration
logging.info("Loading configuration...")
configuration = paasmaker.configuration.Configuration()
configuration.dump()

# Reset the log level.
logging.info("Resetting server log level to %s.", configuration.get_global('server_log_level'))
logger = logging.getLogger()
logger.setLevel(getattr(logging, configuration.get_global('server_log_level')))

# Configure our application and routes.
logging.info("Building routes.")
route_extras = dict(configuration=configuration)
routes = []
routes.extend(paasmaker.controller.example.Example.get_routes(route_extras))
routes.extend(paasmaker.controller.information.Information.get_routes(route_extras))

# Set up the application object.
logging.info("Setting up the application.")
application_settings = configuration.get_torando_configuration()
application = tornado.web.Application(routes, **application_settings)

# Commence the application.
if __name__ == "__main__":
	application.listen(configuration.get_global('http_port'))
	logging.info("Listening on port %d", configuration.get_global('http_port'))
	tornado.ioloop.IOLoop.instance().start()
