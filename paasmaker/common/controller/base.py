import logging
import warnings
import os
import json
import time
import math

import paasmaker
from ..testhelpers import TestHelpers
from ..core import constants

import tornado.testing
import tornado.web
import tornado.websocket
import tornado.escape
import colander
import sqlalchemy

# Types of API requests.
# 1. Node->Node. (ie, nodes talking to each other)
# 2. User->Pacemaker (cookie auth) (ie, AJAX browser callback)
# 3. User->Pacemaker (token auth) (ie, command line tool or other API request)

# Structure of API requests.
# auth: { method: 'node|cookie|token', value: 'token|cookie' }
# data: { ... keys ... }

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

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
	Base controller class, that all other HTTP controllers should
	decend from.

	Provides the following services:

	* Access control, specifying what methods of authentication
	  are valid for the controller.
	* Input parsing, transparently converting standard form encoded
	  POST requests and JSON encoded POST requests in the same way.
	* Output transformations, returning either JSON or HTML as
	  requested.

	The ExampleController shows basic ways to use the base controller.
	"""
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2
	SUPER = 3

	# You must override this in your subclass.
	AUTH_METHODS = []

	# Shared permissions cache for all controllers.
	# Why no locking? We're relying on the Python GIL to sort
	# this out for us.
	PERMISSIONS_CACHE = {}

	def initialize(self, configuration=None, io_loop=None):
		# This is defined here so controllers can change it per-request.
		self.DEFAULT_PAGE_SIZE = 10

		self.configuration = configuration
		self.data = {}
		self.template = {}
		self.errors = []
		self.warnings = []
		self.format = 'html'
		self.root_data = {}
		self.session = None
		self.user = None
		self.auth = {}
		self.params = {}
		self.raw_params = {}
		self.super_auth = False
		self.io_loop = io_loop or tornado.ioloop.IOLoop.instance()

		self.add_data_template('format_form_error', self.format_form_error)
		self.add_data_template('nice_state', self.nice_state)

		# Add a header that is our node's UUID.
		uuid = self.configuration.get_node_uuid()
		if uuid:
			self.add_header('X-Paasmaker-Node', self.configuration.get_node_uuid())

	def prepare(self):
		"""
		Called to prepare the request, before the method that will
		handle the request itself.

		Performs several actions:

		* Parses and stores a JSON POST body if present.
		* Sets the format flag based on the query string.
		* Checks that the user is authenticated with a valid
		  authentication method, and terminates the request
		  with a 403 if it can't find a suitable method.
		"""
		self._set_format(self.get_argument('format', 'html'))

		if self.request.method == 'POST':
			# If the post body is JSON, parse it and put it into the arguments.
			# TODO: This JSON detection is lightweight, but there might be corner
			# cases in it too...
			if len(self.request.body) > 0 and self.request.body[0] == '{' and self.request.body[-1] == '}':
				parsed = json.loads(self.request.body)
				schema = APIRequestSchema()
				try:
					result = schema.deserialize(parsed)
				except colander.Invalid, ex:
					self.send_error(400, exc_info=ex)
					return
				self.auth = result['auth']
				self.raw_params.update(result['data'])

		# Unpack the request arguments into raw params.
		# This is so it behaves just like an API request as well.
		# We also unflatten it here, to make it into a data structure.
		# TODO: Properly unit test this.
		pairs = []
		for k, v in self.request.arguments.iteritems():
			for value in v:
				pairs.append((k, value))
		ftzr = paasmaker.util.flattenizr.Flattenizr()
		structure = ftzr.unflatten(pairs)
		# TODO: This could allow GET variables to replace POST variables...
		# TODO: This means GET variables can override values in the JSON structure.
		self.raw_params.update(structure)

		# Must be one of the supported auth methods.
		self.require_authentication(self.AUTH_METHODS)

	def validate_data(self, api_schema, html_schema=None):
		"""
		Validate the supplied POST data with the given schema.
		In the case of JSON requests, terminate the request immediately
		if the data is invalid. In the case of HTML requests,
		set a validation failed error message, and then
		return False - it's up to the caller to check this
		value and handle it as appropriate. The reason that HTML
		requests return False is that it then gives the controller
		the ability to redisplay the form with the users data in it,
		ready for another attempt.

		:arg SchemaNode api_schema: The API schema to validate against.
		:arg SchemaNode html_schema: The optional HTML schema to validate
			against. If not supplied, the API schema is used regardless of
			the request mode.
		"""
		# Select the real schema to use.
		schema = api_schema
		if self.format == 'html' and html_schema:
			schema = html_schema

		try:
			self.params.update(schema.deserialize(self.raw_params))
		except colander.Invalid, ex:
			logger.error("Invalid data supplied to this controller.")
			logger.error(ex)
			# Store and return the individual errors.
			self.add_data('input_errors', ex.asdict())
			if self.format == 'html':
				self.add_error("There was an error with the input.")
				# Now, copy in the data anyway - as this is the data
				# used to rebuild the forms if needed. The caller MUST
				# heed the fact that the data is invalid.
				self.params = self.raw_params
				return False
			else:
				self.add_error('Invalid data supplied.')
				# This will terminate the request, and also
				# in the returned body should be JSON with a
				# description of the errors.
				raise tornado.web.HTTPError(400, 'Invalid data supplied.')

		return True

	def redirect(self, target, **kwargs):
		"""
		Perform a redirect to the given target URL.

		If the request is a JSON formatted request, this immediately
		returns JSON and returns a 200 code, instead of a redirect.

		:arg str target: The target URI.
		"""
		if self.format == 'html':
			# Only actually redirect in HTML mode - we don't need to redirect API requests.
			super(BaseController, self).redirect(target, **kwargs)
		else:
			self.render("api/apionly.html")

	def require_authentication(self, methods):
		"""
		Check the authentication methods until one is found that
		can be satisfied. In HTML mode, redirects to the login page.
		In JSON mode, it returns a 403 error and terminates the request.
		"""
		if len(methods) == 0:
			# No methods provided.
			raise tornado.web.HTTPError(403, 'Access is denied. No authentication methods supplied. This is a server side coding error.')

		found_allowed_method = False

		if self.ANONYMOUS in methods:
			# Anonymous is allowed. So let it go through...
			logger.debug("Anonymous method allowed. Allowing request.")
			found_allowed_method = True

		if self.NODE in methods:
			# Check that a valid node authenticated.
			logger.debug("Checking node authentication.")
			node_allowed = self.check_node_auth()
			if node_allowed:
				found_allowed_method = True
			logger.debug("Node authentication: %s", str(node_allowed))

		if self.SUPER in methods:
			# Check that a valid super key was supplied.
			logger.debug("Checking super authentication.")
			super_allowed = self.check_super_auth()
			if super_allowed:
				found_allowed_method = True
				self.super_auth = True
			logger.debug("Super authentication: %s", str(super_allowed))

		if self.USER in methods:
			# Check that a valid user is authenticated.
			logger.debug("Checking user authentication.")
			user_allowed = self.get_current_user()
			if user_allowed:
				found_allowed_method = True

			logger.debug("User authentication: %s", user_allowed)

		if not found_allowed_method:
			# YOU ... SHALL NOT ... PAAS!
			# (But with less bridge breaking.)
			logger.warning("Access denied for request.")
			if self.format == 'json':
				raise tornado.web.HTTPError(403, 'Access is denied')
			else:
				self.redirect('/login?rt=' + tornado.escape.url_escape(self.request.uri))

	def check_node_auth(self):
		"""
		Check to see if the node authentication is valid.
		"""
		auth_using_header = self.request.headers.has_key('Node-Token')
		if auth_using_header:
			if self.request.headers['node-token'] == self.configuration.get_flat('node_token'):
				return True
		if self.auth.has_key('method') and self.auth['method'] == 'node':
			if self.auth.has_key('value') and self.auth['value'] == self.configuration.get_flat('node_token'):
				return True
		return False

	def check_super_auth(self):
		"""
		Check to see if the super authentication is valid.
		"""
		if self.configuration.is_pacemaker() and self.configuration.get_flat('pacemaker.allow_supertoken'):
			if self.auth.has_key('method') and self.auth['method'] == 'super':
				if self.auth.has_key('value') and self.auth['value'] == self.configuration.get_flat('pacemaker.super_token'):
					return True
			auth_using_header = self.request.headers.has_key('Super-Token')
			if auth_using_header:
				if self.request.headers['super-token'] == self.configuration.get_flat('pacemaker.super_token'):
					return True
		return False

	def get_current_user(self):
		"""
		Get the currently logged in user.
		"""
		# Did we already look them up? Return that.
		if self.user:
			return self.user

		# Only pacemakers allow users to authenticate to them.
		if not self.configuration.is_pacemaker():
			return None

		# See if we're using token authentication.
		test_token = None
		auth_using_token = self.auth.has_key('method') and self.auth['method'] == 'token'
		if auth_using_token and self.auth.has_key('value'):
			test_token = self.auth['value']
		auth_using_header = self.request.headers.has_key('User-Token')
		if auth_using_header:
			test_token = self.request.headers['user-token']
		if auth_using_token or auth_using_header:
			if test_token:
				# Lookup the user object.
				user = self.db().query(paasmaker.model.User) \
					.filter(paasmaker.model.User.apikey==test_token).first()
				# Make sure we have the user, and it's enabled and not deleted.
				if user and user.enabled and not user.deleted:
					self.user = user

		# Fetch their cookie.
		raw = self.get_secure_cookie('user', max_age_days=self.configuration.get_flat('pacemaker.login_age'))
		if raw:
			# Lookup the user object.
			user = self.db().query(paasmaker.model.User).get(int(raw))
			# Make sure we have the user, and it's enabled and not deleted.
			if user and user.enabled and not user.deleted:
				self.user = user

		# Update their permissions cache. The idea is to do
		# one SQL query per request to check it, and 2 if
		# the permissions have changed - the second one is to
		# update the permissions.
		# TODO: The cache class is tested via the model unit tests,
		# but add a few more unit tests to make sure that this works properly.
		if self.user:
			user_key = str(self.user.id)
			if not self.PERMISSIONS_CACHE.has_key(user_key):
				self.PERMISSIONS_CACHE[user_key] = paasmaker.model.WorkspaceUserRoleFlatCache(user)
			self.PERMISSIONS_CACHE[user_key].check_cache(self.db())

		return self.user

	def has_permission(self, permission, workspace=None, user=None):
		"""
		Determine if the currently logged in user has the named
		permission. Returns True if they do, or False otherwise.

		:arg str permission: The permission to check for.
		:arg Workspace workspace: The optional workspace to limit
			the scope to.
		:arg User user: The optional user to compare for, rather
			than the logged in user.
		"""
		if not user and self.super_auth:
			# If authenticated with the super token,
			# you can do anything. With great power comes
			# great responsiblity...
			return True
		if not user:
			# No user supplied? Use the current user.
			user = self.get_current_user()
		if not user:
			# Still no user? Not logged in.
			# This situation should not occur, because the parent
			# controller is protected.
			raise tornado.web.HTTPError(403, "Not logged in.")

		# NOTE: Nodes are not checked to see if they have permission,
		# as they're only permitted to access a few controllers anyway.
		# They're assigned permission by being able to authenticate
		# to some controllers.

		allowed = self.PERMISSIONS_CACHE[str(user.id)].has_permission(
			permission,
			workspace
		)
		return allowed

	def require_permission(self, permission, workspace=None, user=None):
		"""
		Require the given permission to continue. Stops the request
		with a 403 if the user is not granted the given permission.

		:arg str permission: The permission to check for.
		:arg Workspace workspace: The optional workspace to limit the
			scope to.
		:arg User user: The optional user to check the permission for.
		"""
		allowed = self.has_permission(permission, workspace, user)
		if not allowed:
			self.add_error("You require permission %s to access." % permission)
			raise tornado.web.HTTPError(403, "Access denied.")

	def add_data(self, key, value):
		"""
		Add a named data key to this request, that will then appear
		in the output. If the request is JSON, it forms a key in the
		dict that is generated for it's output. If the request is HTML,
		then it is available in the template with the supplied name.

		If key already exists, it's value is overwritten.

		:arg str key: The name of the value.
		:arg object value: The value.
		"""
		self.data[key] = value

	def add_data_template(self, key, value):
		"""
		Add a named data key to this request. Keys added with this
		method will only be available to the template, and never returned
		to clients requesting via JSON. This allows you to add data for
		the template that might be privileged, which would be undesirable
		to add to the JSON output. Also, it can be used to add functions
		for use in templates, for which it would make no sense to return as
		JSON.
		"""
		self.template[key] = value

	def get_data(self, key):
		"""
		Get an existing data key previously added with ``add_data()``. Raises
		a ``KeyError`` if not found.
		"""
		return self.data[key]

	def get_data_template(self, key):
		"""
		Get an existing template data key previously added with
		``add_data_template()``. Raises a ``KeyError`` if not found.
		"""
		return self.template[key]

	def format_form_error(self, field):
		"""
		Helper function supplied to the templates that format errors
		for a named form field.

		Assumes that the data has an 'input_errors' key,
		that maps to a list of errors for that field.

		:arg str field: The field to display the errors for.
		"""
		if self.data.has_key('input_errors') and self.data['input_errors'].has_key(field):
			return '<ul class="error"><li>%s</li></ul>' % tornado.escape.xhtml_escape(self.data['input_errors'][field])
		else:
			return ''

	def nice_state(self, state):
		"""
		Helper function supplied to templates that formats a state
		string a little bit nicer. Basically, converts it to lower case
		and capitalizes only the first letter.

		:arg str state: The state to format.
		"""
		return state[0] + state[1:].lower()

	def add_error(self, error):
		"""
		Add an error to the request.

		:arg str error: The error message.
		"""
		self.errors.append(error)
	def add_errors(self, errors):
		"""
		Add several errors to the request.

		:arg list errors: The errors to add.
		"""
		self.errors.extend(errors)

	def add_warning(self, warning):
		"""
		Add a warning to this request.

		:arg str warning: The warning to add.
		"""
		self.warnings.append(warning)
	def add_warnings(self, warnings):
		"""
		Add several warnings to this request.

		:arg list warnings: The list of warnings to add.
		"""
		self.warnings.extend(warnings)

	def db(self):
		"""
		Fetch a SQLAlchemy database session.

		Each request returns only one Session object. If you call
		``db()`` several times during a request, each one will be
		the same Session object.
		"""
		if self.session:
			return self.session
		self.session = self.configuration.get_database_session()
		return self.session

	def _set_format(self, format):
		if format != 'json' and format != 'html':
			raise ValueError("Invalid format '%s' supplied." % format)
		self.format = format

	def render(self, template, **kwargs):
		"""
		Render the response to the client, and finish the request.

		The template supplied is the name of the template file
		to use when in HTML mode. If the request is in JSON
		mode, the template is ignored and instead JSON is output to
		the client.
		"""
		# Prepare our variables.
		if self.format == 'json':
			variables = {}
			variables.update(self.root_data)
			variables['data'] = self.data
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			self.set_header('Content-Type', 'application/json')
			self.write(json.dumps(variables, cls=paasmaker.util.jsonencoder.JsonEncoder))
			# The super classes render() calls finish at this stage,
			# so we do so here.
			self.finish()
		elif self.format == 'html':
			variables = self.data
			variables.update(self.root_data)
			variables['errors'] = self.errors
			variables['warnings'] = self.warnings
			variables.update(self.template)
			variables.update(kwargs)
			variables['PERMISSION'] = constants.PERMISSION
			variables['has_permission'] = self.has_permission
			super(BaseController, self).render(template, **variables)

	def write_error(self, status_code, **kwargs):
		"""
		Write an error and terminate the request. You can use this
		to finish your request early, although flow continues past
		this function.

		This renders an error template with error data. It discards
		all other data added with ``add_data()``.

		:arg int status_code: The HTTP status code to send.
		"""
		# Reset the data queued up until now.
		# Except for input_errors.
		if self.data.has_key('input_errors'):
			self.data = {'input_errors': self.data['input_errors']}
		else:
			self.data = {}
		self.root_data['error_code'] = status_code
		if kwargs.has_key('exc_info'):
			self.add_error('Exception: ' + str(kwargs['exc_info'][0]) + ': ' + str(kwargs['exc_info'][1]))
		self.set_status(status_code)
		self.render('error/error.html')

	def on_finish(self):
		self.application.log_request(self)

	def _get_router_stats_for(self, name, input_id, callback, output_key='router_stats', title=None):
		"""
		Helper function to get the aggregated router stats for
		the named aggregation group. Places the result automatically
		into the given output key, with the given title.

		:arg str name: The aggregation name.
		:arg int input_id: The aggregation input ID.
		:arg callable callback: The callback to call when it's done.
			It's single argument is the stats data.
		:arg str output_key: The output key name to insert the data
			as. If None, does not add the data at all, and only
			calls the callback with the data.
		:arg str title: The optional title to give this set of data.
		"""
		router_stats = paasmaker.router.stats.ApplicationStats(
			self.configuration
		)

		output = {
			'name': name,
			'input_id': input_id,
			'title': title,
			'data': None
		}

		if output_key:
			self.add_data(output_key, output)

		self.add_data_template('router_stats_display', paasmaker.router.stats.ApplicationStats.DISPLAY_SET)

		def got_router_stats(result):
			output['data'] = result
			callback(result)

		def router_stats_error(error, exception=None):
			self.add_warning('Unable to fetch router stats: ' + error)
			callback(None)

		def got_router_vtset(vtset):
			router_stats.total_for_list(
				vtset,
				got_router_stats,
				router_stats_error
			)

		def stats_system_ready():
			router_stats.vtset_for_name(
				name,
				input_id,
				got_router_vtset
			)

		router_stats.setup(
			stats_system_ready,
			router_stats_error
		)

	def _redirect_job(self, job_id, url):
		"""
		Helper function to redirect to the job detail page
		for the given job ID. The supplied URL is used as
		the return URL.

		:arg str job_id: The job ID to list for.
		:arg str url: The return URL shown on the detail page.
		"""
		self.redirect("/job/detail/%s?ret=%s" % (
				job_id,
				tornado.escape.url_escape(url)
			)
		)

	def _paginate(self, key, data, page_size=None):
		"""
		Simple paginator for lists of data.

		Using this is as simple as this::

			data = [1, 2, 3]
			self._paginate('data', data)

		In your templates, you can then include the pagination
		template, which will set up links for you to page
		between the data. In JSON requests, it will by default
		return all results. However, if you pass the ``pagesize``
		query parameter, it will paginate the data in pages
		of that size.

		This will read the query string parameter ``page`` to
		determine what page to show. For this reason, you'll
		only want to use one call to ``_paginate()`` per request
		handler.

		Your controller can change the default page size for
		by setting the class variable DEFAULT_PAGE_SIZE.

		The key that is added to the data has several sub
		keys, used to show information about the data.

		* total: The total number of entries.
		* pages: The total number of pages.
		* page: This page, starting at 1.
		* start: The first record number (starting at 1).
		* end: The last record number (ending at total).
		"""
		page = 1
		page_size = self.DEFAULT_PAGE_SIZE

		if self.raw_params.has_key('page'):
			try:
				page = int(self.raw_params['page'])
			except ValueError, ex:
				# Invalid, ignore.
				pass
		if self.raw_params.has_key('pagesize'):
			try:
				page_size = int(self.raw_params['pagesize'])
			except ValueError, ex:
				# Invalid, ignore.
				pass

		if isinstance(data, sqlalchemy.orm.query.Query):
			total = data.count()
		else:
			total = len(data)

		# For JSON requests, by default, don't paginate, as
		# this would be very confusing.
		# If the JSON request supplies a pagesize, then we
		# will start paginating.
		if self.format != 'html' and not self.raw_params.has_key('pagesize'):
			page_size = total

		pages = 0
		if total > 0:
			pages = int(math.ceil(float(total) / float(page_size)))
		start = (page - 1) * page_size
		end = min(page * page_size, total)

		page_data = {
			'total': total,
			'pages': pages,
			'page': page,
			'start': start + 1,
			'end': end
		}
		self.add_data('%s_pagination' % key, page_data)
		self.add_data(key, data[start:end])

# A schema for websocket incoming messages, to keep them consistent.
class WebsocketMessageSchemaCookie(colander.MappingSchema):
	request = colander.SchemaNode(colander.String(),
		title="Request",
		description="What is intended from this request")
	sequence = colander.SchemaNode(colander.Integer(),
		title="Sequence",
		description="The sequence number for this request. Errors are returned matching this sequence, so you can tell which request they originated from. Optional",
		default=0,
		missing=0)
	data = colander.SchemaNode(colander.Mapping(unknown='preserve'))

class WebsocketMessageSchemaNormal(WebsocketMessageSchemaCookie):
	auth = APIAuthRequestSchema()

class BaseWebsocketHandler(tornado.websocket.WebSocketHandler):
	"""
	Base class for WebsocketHandlers.

	This base class handles authentication, parsing incoming messages,
	and sending back messages and errors.
	"""
	# Allowed authentication methods.
	ANONYMOUS = 0
	NODE = 1
	USER = 2
	SUPER = 3

	# You must override this in your subclass.
	AUTH_METHODS = []

	def initialize(self, configuration):
		"""
		Called by Tornado when the connection is established.
		"""
		self.configuration = configuration
		self.authenticated = False

	def parse_message(self, message):
		"""
		Helper function to parse a message. This function
		only validates it against the full schema, and then
		attempts to check the user's authentication. If the
		authentication fails or the message headers do not
		validate, an error is sent back to the client.

		Otherwise, the parsed message is returned.

		:arg str message: The raw message from the client.
		"""
		parsed = json.loads(message)
		schema = WebsocketMessageSchemaNormal()

		# See if there was a user cookie passed. If so, it's valid.
		# TODO: Permissions.
		# TODO: If this is not a pacemaker, handle that properly.
		raw = self.get_secure_cookie('user', max_age_days=self.configuration.get_flat('pacemaker.login_age'))
		if raw:
			# Lookup the user object.
			# TODO: This uses up a database session?
			user = self.configuration.get_database_session().query(paasmaker.model.User).get(int(raw))
			# Make sure we have the user, and it's enabled and not deleted.
			if user and user.enabled and not user.deleted:
				self.user = user
				self.authenticated = True
				schema = WebsocketMessageSchemaCookie()

		try:
			result = schema.deserialize(parsed)

			# Validate their authentication details.
			# Only required the first time - every subsequent message
			# they'll be considered authenticated.
			if self.authenticated:
				return result
			else:
				self.check_authentication(result['auth'], result)
				if self.authenticated:
					return result
				else:
					return None
		except colander.Invalid, ex:
			if not parsed.has_key('sequence'):
				parsed['sequence'] = -1
			self.send_error(str(ex), parsed)
			return None

	def check_authentication(self, auth, message):
		"""
		Check the authentication of the message. This is called
		by ``parse_message()``.
		"""
		if len(self.AUTH_METHODS) == 0:
			# No methods provided.
			self.send_error('Access is denied. No authentication methods supplied. This is a server side coding error.', message)
			return

		found_allowed_method = False

		if self.ANONYMOUS in self.AUTH_METHODS:
			# Anonymous is allowed. So let it go through...
			found_allowed_method = True

		if self.NODE in self.AUTH_METHODS:
			# Check that a valid node authentication.
			if auth.has_key('method') and auth['method'] == 'node':
				if auth.has_key('value') and auth['value'] == self.configuration.get_flat('node_token'):
					found_allowed_method = True

		if self.SUPER in self.AUTH_METHODS:
			# Check that a valid super authentication.
			if auth.has_key('method') and auth['method'] == 'super' and self.configuration.get_flat('pacemaker.allow_supertoken'):
				if auth.has_key('value') and auth['value'] == self.configuration.get_flat('pacemaker.super_token'):
					found_allowed_method = True

		if self.USER in self.AUTH_METHODS:
			test_token = None
			if auth.has_key('method') and auth['method'] == 'token':
				test_token = auth['value']
			if test_token:
				# Lookup the user object.
				user = self.configuration.get_database_session().query(paasmaker.model.User) \
					.filter(paasmaker.model.User.apikey==test_token).first()
				# Make sure we have the user, and it's enabled and not deleted.
				if user and user.enabled and not user.deleted:
					found_allowed_method = True

		# TODO: Handle user token authentication.
		if not found_allowed_method:
			self.send_error('Access is denied. Authentication failed.', message)
		else:
			self.authenticated = True

	def validate_data(self, message, schema):
		"""
		Validate parsed data with the given schema. If this
		succeeds, the resulting deserialized data is returned.
		If it fails, an error is sent back to the client
		and None is returned.

		:arg dict message: The message body.
		:arg SchemaNode schema: The colander schema to validate
			against.
		"""
		try:
			result = schema.deserialize(message['data'])
		except colander.Invalid, ex:
			self.send_error(str(ex), message)
			return None

		return result

	def send_error(self, error, message):
		"""
		Send an error back to the client, framing it
		with the sequence number from the original message.

		:arg str error: The error message.
		:arg dict message: The parsed original message body.
		"""
		error_payload = self.make_error(error, message)
		error_message = self.encode_message(error_payload)
		self.write_message(error_message)

	def send_success(self, typ, data):
		"""
		Send a successful response to the client, handling
		encoding and framing.

		:arg str typ: The type of the message returned.
		:arg dict data: The data to return to the client.
		"""
		self.write_message(self.encode_message(self.make_success(typ, data)))

	def make_error(self, error, message):
		"""
		Helper function to build an error frame.
		"""
		result = {
			'type': 'error',
			'data': { 'error': error, 'sequence': message['sequence'] }
		}
		return result

	def make_success(self, typ, data):
		"""
		Helper function to build a successful data frame.
		"""
		message = {
			'type': typ,
			'data': data
		}
		return message

	def encode_message(self, message):
		"""
		Helper function to encode a message.
		"""
		return json.dumps(message, cls=paasmaker.util.jsonencoder.JsonEncoder)

class BaseControllerTest(tornado.testing.AsyncHTTPTestCase, TestHelpers):

	config_modules = []

	def late_init_configuration(self, io_loop):
		"""
		Late initialize configuration. This is to solve the chicken-and-egg issue of getting
		this unit tests test HTTP port.
		"""
		if not self.configuration:
			self.configuration = paasmaker.common.configuration.ConfigurationStub(
				port=self.get_http_port(),
				modules=self.config_modules,
				io_loop=io_loop)
		return self.configuration

	def setUp(self):
		self.configuration = None
		self._port = None
		self.test_port_allocator = paasmaker.util.port.FreePortFinder()

		super(BaseControllerTest, self).setUp()
		self.configuration.setup_job_watcher()

	def tearDown(self):
		self.configuration.cleanup()
		super(BaseControllerTest, self).tearDown()

	def get_http_port(self):
		"""Returns the port used by the server.

		A new port is chosen for each test.
		"""
		if self._port is None:
			self._port = self.test_port_allocator.free_in_range(10100, 10199)
		return self._port

	def fetch_with_user_auth(self, url, **kwargs):
		"""
		Fetch the given URL as a user, creating a user to authenticate as
		if needed.

		Calls self.stop when the request is ready, so your unit test should
		call self.wait() for the response.

		If URL contains '%d', this is replaced with the test HTTP port.
		Otherwise, the URL is untouched.
		"""
		# Create a test user - if required.
		s = self.configuration.get_database_session()
		user = s.query(paasmaker.model.User) \
			.filter(paasmaker.model.User.login=='username') \
			.first()

		if not user:
			# Not found. Make one.
			u = paasmaker.model.User()
			u.login = 'username'
			u.email = 'username@example.com'
			u.name = 'User Name'
			u.password = 'testtest'
			s.add(u)

			# Allow them to do anything.
			# TODO: This makes for a poor test.
			r = paasmaker.model.Role()
			r.name = 'Test'
			r.permissions = paasmaker.common.core.constants.PERMISSION.ALL
			s.add(r)

			a = paasmaker.model.WorkspaceUserRole()
			a.user = u
			a.role = r

			paasmaker.model.WorkspaceUserRoleFlat.build_flat_table(s)
			s.refresh(u)

		# Ok, now that we've done that, try to log in.
		request = paasmaker.common.api.LoginAPIRequest(self.configuration)
		request.set_credentials('username', 'testtest')
		request.send(self.stop)
		response = self.wait()
		if not response.success:
			raise Exception('Failed to login as test user.')

		# Athenticate the next request.
		if not kwargs.has_key('headers'):
			kwargs['headers'] = {}
		kwargs['headers']['Cookie'] = 'user=' + response.data['token']

		# Add a cookie header.
		resolved_url = url
		if url.find('%d') > 0:
			resolved_url = resolved_url % self.get_http_port()
		request = tornado.httpclient.HTTPRequest(resolved_url, **kwargs)
		client = tornado.httpclient.AsyncHTTPClient(io_loop=self.io_loop)
		client.fetch(request, self.stop)
