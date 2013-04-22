define([
	'underscore',
	'backbone',
	'models/workspace'
], function(_, Backbone, WorkspaceModel){
	var WorkspaceCollection = Backbone.Collection.extend({
		model: WorkspaceModel,
		url: '/workspace/list?format=json',
		parse: function(response) {
			return response.data.workspaces;
		}
	});

	return WorkspaceCollection;
});