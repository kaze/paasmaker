define([
	'jquery',
	'underscore',
	'backbone',
	'context',
	'tpl!templates/workspace/header.html'
], function($, _, Backbone, context, headerListViewTemplate){
	var WorkspaceHeaderListView = Backbone.View.extend({
		initialize: function() {
			// Render a blank template to start off with.
			this.$el.html(headerListViewTemplate({workspaces: []}));

			// And when the data comes in, update the whole list.
			this.collection.on('sync', _.bind(this.render, this));
		},
		render: function() {
			// Render the entire list.
			this.$el.html(headerListViewTemplate({workspaces: this.collection.models}));
		},
		events: {
			"click a": "navigateAway",
		},
		navigateAway: function(arg) {
			this.$el.parent().removeClass('open');
			context.router.navigate($(arg.currentTarget).attr('href'), { trigger: true });

			return false;
		}
	});

	return WorkspaceHeaderListView;
});