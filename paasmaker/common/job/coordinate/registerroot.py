
import os
import subprocess
import uuid
import socket

import paasmaker
from paasmaker.common.core import constants
from ..base import BaseJob
from ...testhelpers import TestHelpers
from startuproot import StartupRootJob
from shutdownroot import ShutdownRootJob

import tornado
from pubsub import pub

# TODO: Implement abort features for all of these jobs.

class RegisterRootJob(BaseJob):
	@staticmethod
	def setup(configuration, application_instance_type_id, callback):
		# Set up the context.
		context = {}
		context['application_instance_type_id'] = application_instance_type_id

		def on_root_job_added(root_job_id):
			def on_select_locations(select_locations_job_id):
				# Done! Callback with the root ID.
				callback(root_job_id)
				# end on_select_locations

			def on_registration_requests(registration_request_job_id):
				# And select the locations for instance.
				configuration.job_manager.add_job(
					'paasmaker.job.coordinate.selectlocations',
					{},
					"Select instance locations",
					on_select_locations,
					parent=registration_request_job_id
				)
				# end on_registration_requests

			# And a job to send register requests to nodes.
			configuration.job_manager.add_job(
				'paasmaker.job.coordinate.registerrequest',
				{},
				"Registration requests",
				on_registration_requests,
				parent=root_job_id
			)
			# end on_root_job_added

		configuration.job_manager.add_job(
			'paasmaker.job.coordinate.registerroot',
			{},
			"Select locations and register instances",
			on_root_job_added,
			context=context
		)

	def start_job(self, context):
		self.logger.info("Select locations and register instances.")
		self.success({}, "Selected and registered instances.")

class RegisterRootJobTest(tornado.testing.AsyncTestCase, TestHelpers):
	def setUp(self):
		super(RegisterRootJobTest, self).setUp()
		self.configuration = paasmaker.common.configuration.ConfigurationStub(0, ['pacemaker', 'heart'], io_loop=self.io_loop)
		self.configuration.set_node_uuid(str(uuid.uuid4()))
		# Fire up the job manager.
		self.configuration.startup_job_manager(self.stop)
		self.wait()

	def tearDown(self):
		self.configuration.cleanup()
		super(RegisterRootJobTest, self).tearDown()

	def on_job_status(self, message):
		#print str(message.flatten())
		self.stop(message)

	def on_job_catchall(self, message):
		# This is for debugging.
		#print str(message.flatten())
		pass

	def test_simple(self):
		runtime_parameters = {
			'launch_command': "python app.py --port=%(port)d"
		}
		instance_type = self.create_sample_application(
			self.configuration,
			'paasmaker.runtime.shell',
			runtime_parameters,
			'1',
			'tornado-simple'
		)
		node = self.add_simple_node(self.configuration.get_database_session(), {
			'node': {},
			'runtimes': {
				'paasmaker.runtime.shell': ['1']
			}
		}, self.configuration)

		RegisterRootJob.setup(
			self.configuration,
			instance_type.id,
			self.stop
		)

		root_job_id = self.wait()

		# Subscribe to updates to the root job.
		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(root_job_id))
		pub.subscribe(self.on_job_catchall, 'job.status')

		# And make it work.
		self.configuration.job_manager.allow_execution(root_job_id, self.stop)
		self.wait()

		self.short_wait_hack(length=1)

		#print
		#self.dump_job_tree(root_job_id)
		#self.wait()

		result = self.wait()
		while result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		session = self.configuration.get_database_session()
		instances = session.query(
			paasmaker.model.ApplicationInstance
		).filter(
			paasmaker.model.ApplicationInstance.application_instance_type == instance_type,
			paasmaker.model.ApplicationInstance.state == constants.INSTANCE.REGISTERED
		)

		# Verify the instance was set up.
		self.assertEquals(instances.count(), 1, "Should have one registered instance.")
		self.assertTrue(instances[0].port in range(42600, 42699), "Port not in expected range.")

		# Now, hijack this test to test startup of instance. And other stuff.
		StartupRootJob.setup(
			self.configuration,
			instance_type.id,
			self.stop
		)
		startup_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(startup_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(startup_root_id, self.stop)
		self.wait()

		self.short_wait_hack()

		#print
		#self.dump_job_tree(startup_root_id)
		#self.wait()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# Confirm that the entry exists in the routing table.
		self.configuration.get_router_table_redis(self.stop, None)
		redis = self.wait()

		set_key_version_1 = "instances_1.foo.com.%s" % self.configuration.get_flat('pacemaker.cluster_hostname')
		version_instance = "%s:%d" % (socket.gethostbyname(instances[0].node.route), instances[0].port)

		redis.smembers(set_key_version_1, self.stop)
		routing_table = self.wait()

		self.assertIn(version_instance, routing_table, "Missing entry from routing table.")

		# HACK: Update the instances to RUNNING state, because the listener that updates
		# the database isn't running at this stage.
		instance = instances[0]
		session.refresh(instance)
		instance.state = constants.INSTANCE.RUNNING
		session.add(instance)
		session.commit()

		# Now shut the instance down.
		ShutdownRootJob.setup(
			self.configuration,
			instance_type.id,
			self.stop
		)
		shutdown_root_id = self.wait()

		pub.subscribe(self.on_job_status, self.configuration.get_job_status_pub_topic(shutdown_root_id))

		# And make it work.
		self.configuration.job_manager.allow_execution(shutdown_root_id, self.stop)
		self.wait()

		self.short_wait_hack()

		result = self.wait()
		while result is None or result.state != constants.JOB.SUCCESS:
			result = self.wait()

		self.assertEquals(result.state, constants.JOB.SUCCESS, "Should have succeeded.")

		# To check: that the instance is marked as STOPPED.
		instance_data = self.configuration.instances.get_instance(instance.instance_id)
		self.assertEquals(instance_data['instance']['state'], constants.INSTANCE.STOPPED, "Instance not in correct state.")

		# That it's no longer in the routing table.
		redis.smembers(set_key_version_1, self.stop)
		routing_table = self.wait()
		self.assertNotIn(version_instance, routing_table, "Additional entry from routing table.")