/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.admin.js - interface for administration pages
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling

pm.admin = {};

pm.admin.profile = (function() {
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'profile',
				callback: function(data) {
					$('#main').html(pm.handlebars.user_profile({ current_user: data }));
				}
			});
		}
	};
}());

pm.admin.plugins = (function() {
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'configuration/plugins',
				callback: function(data) {
					var valid_plugins = [];
				
					for (var key in data.plugins) {
						var item = data.plugins[key];
						if (item.modes.indexOf('JOB') === -1) {
							if (Object.keys(item.options).length > 0) {
								item.options = JSON.stringify(item.options, undefined, 4);
							} else {
								item.options = '';
							}
						
							valid_plugins.push(item);
						}
					}
				
					$('#main').html(pm.handlebars.configuration_plugins({ plugins: valid_plugins }));
				}
			});
		}
	};
}());

pm.admin.config_dump = (function() {
	return {
		switchTo: function() {
			pm.data.api({
				endpoint: 'configuration/dump',
				callback: function(data) {
					var config_string = JSON.stringify(data.configuration, undefined, 4);
				
					$('#main').html(pm.handlebars.configuration_dump({ configuration: config_string }));
				}
			});
		}
	};
}());
