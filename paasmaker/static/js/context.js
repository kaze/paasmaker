define([
	'jquery',
	'underscore',
	'backbone',
	'collections/workspaces',
	'collections/nodes'
], function($, _, Backbone, WorkspaceCollection, NodeCollection) {
	var module = {};
	module.dispatcher = _.clone(Backbone.Events);
	module.workspaces = new WorkspaceCollection();
	module.nodes = new NodeCollection();

	module.navigate = function(url) {
		module.router.navigate(url, {trigger: true});
	};

	module.hasPermission = function(permission, workspace_id, table) {
		// From the given table, figure out if the user has that
		// permission or not.
		// permission: the string permission name.
		// workspace_id: if supplied, should be an integer that is the
		//   workspace ID to limit the request to.
		// table: an object of values from the server.

		if(!table) {
			// Use the server-supplied permissions table.
			table = permissions;
		}

		var testKeys = [];
		if(workspace_id) {
			testKeys.push('' + workspace_id + '_' + permission);
		}
		testKeys.push('None_' + permission);

		for(var i = 0; i < testKeys.length; i++) {
			if(table[testKeys[i]]) {
				return true;
			}
		}

		return false;
	};

	module.initialize = function() {
		// Load the workspaces from the containing page.
		module.workspaces.reset(workspaces);
	};

	module.loadPlugin = function(pluginName, callback) {
		var moduleName = 'plugin/' + pluginName + '/script'
		require([moduleName], function(loadedPlugin) {
			var completedInit = function() {
				if (callback) {
					callback(loadedPlugin);
				}
			};

			// Have we already loaded it? If so, we would have set a
			// called_name attribute on the module.
			if(!loadedPlugin._called_name) {
				// Load the CSS as well. This might 404 but that's ok.
				var cssPath = '/plugin/' + pluginName + '/stylesheet.css';
				$('head').append('<link href="' + cssPath + '" rel="stylesheet">');

				// Get the module to initalize itself.
				loadedPlugin._called_name = pluginName;
				loadedPlugin._resource_path = '/plugin/' + pluginName + '/';

				loadedPlugin.initialize(loadedPlugin._called_name, loadedPlugin._resource_path, completedInit);
			} else {
				completedInit();
			}
		});
	};

	return module;
});