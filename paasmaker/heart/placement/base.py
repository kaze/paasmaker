

class Base():
	def __init__(self, configuration):
		self.configuration = configuration

	def filter_by_runtime(self, instance, nodes):
		"""
		Filter the list of nodes by the runtime.
		"""
		pass

	def mark_already_running(self, instance, nodes):
		"""
		Mark nodes as already running the given instance
		if they are already running the given instance.
		"""
		pass

	def choose(self, instance, nodes):
		"""
		From the given nodes, attempt to choose a node to place the
		given instance.
		"""
		raise NotImplementedError("You must implement choose().")
