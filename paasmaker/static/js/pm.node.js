/**
 * Paasmaker 0.9.0
 * Insert licence notice here
 *
 * pm.node.js - interfaces for viewing the list of nodes, and individual nodes
 */

if (!window.pm) { var pm = {}; }	// TODO: module handling
if (!pm.node) { pm.node = {}; }

pm.node.list = (function() {
	var bootstrap_state_classes = {
		'ACTIVE': { badge: 'badge-success', icon: 'icon-ok' },
		'STOPPED': { badge: 'badge-warning', icon: 'icon-warning-sign' },
		'INACTIVE': { badge: 'badge-warning', icon: 'icon-warning-sign' },
		'DOWN': { badge: 'badge-important', icon: 'icon-ban-circle' }
	};

	return {
		updateBreadcrumbs: function(data) {
			$('ul.breadcrumb').empty();

			var list_li = $("<li>");
			$('ul.breadcrumb').append(list_li);
			if (data.node || data.suffix) {
				var list_link = $("<a>", { "href": "/node/list" });
				list_li.append(list_link);
				list_link.text("Nodes");
				list_li.append("<span class=\"divider\">&middot;</span>");
			} else {
				list_li.text("Nodes");
			}

			if (data.node) {
				var node_li = $("<li>");
				$('ul.breadcrumb').append(node_li);
				if (data.suffix) {
					var node_link = $("<a>", { "href": "/node/" + data.node.id });
					node_li.append(node_link);
					node_link.text(data.node.name);
					node_li.append("<span class=\"divider\">&middot;</span>");
				} else {
					node_li.text(data.node.name);
				}
			}
			if (data.suffix) {
				$('ul.breadcrumb').append(
					$("<li>").text(data.suffix)
				);
			}
		},

		updateNodeMenu: function(highlight_node_id) {

			pm.data.api({
				endpoint: "node/list",
				callback: function(data) {
					processed_node_list = [];
					data.nodes.forEach(function(node) {
						if (highlight_node_id && highlight_node_id == node.id) {
							node.is_active = true;
						}
						node.state_class = bootstrap_state_classes[node.state];

						node.updated_age = node.updated_age.toFixed(1);
						node.score = node.score.toFixed(2);
						// var last_heard = pm.util.parseDate(node.last_heard);
						// node.updated_age = moment().diff(last_heard, 'seconds');

						processed_node_list.push(node);
					});
					data.nodes = processed_node_list;

					$('#left_menu_wrapper').html(Handlebars.templates.node_menu(data));
				}
			});
		},

		actionButton: function(e) {
			var t = $(e.target);
			if (t.hasClass('node-delete-button')) {
				$('#node_delete_modal').remove();
				$('#main_right_view').append(Handlebars.templates.node_delete({
					name: t.data('node-name'), id: t.data('node-id')
				}));
				$('#node_delete_modal').modal();
			}
		},

		switchTo: function() {
			pm.data.api({
				endpoint: 'node/list',
				callback: function(data) {
					pm.leftmenu.redrawContainers();

					var sorted_nodes = { pacemakers: [], hearts: [], routers: [] };
					data.nodes.forEach(function(node) {
						node.state_class = bootstrap_state_classes[node.state];

						if (node.pacemaker) {
							sorted_nodes.pacemakers.push(node);
						}
						if (node.heart) {
							sorted_nodes.hearts.push(node);
						}
						if (node.router) {
							sorted_nodes.routers.push(node);
						}
					});

					$('#main_right_view').html(Handlebars.templates.node_list(sorted_nodes));

					pm.node.list.updateNodeMenu();
					pm.widgets.uuid.update();

					$('.loading-overlay').remove();
				}
			});
		}

	};
}());


pm.node.detail = (function() {

	return {
		uptimeString: function(start_time) {
			var uptime = moment().diff(start_time, 'seconds');
			var uptime_string = '';
			if (uptime > 86400) {
				var days = Math.floor(uptime/86400);
				uptime_string += days + (days == 1 ? " day, " : " days, ");
				uptime = uptime % 86400;
			}
			if (uptime > 3600) {
				var hours = Math.floor(uptime/3600);
				uptime_string += hours + (hours == 1 ? " hour, " : " hours, ");
				uptime = uptime % 3600;
			}
			if (uptime > 60) {
				var minutes = Math.floor(uptime/60);
				uptime_string += minutes + (minutes == 1 ? " minute, " : " minutes, ");
				uptime = uptime % 60;
			}
			uptime_string += uptime + (uptime == 1 ? " second" : " seconds");

			return uptime_string;
		},

		processNodeData: function(data) {
			data.formatted_tags = JSON.stringify(data.tags, undefined, 4);
			data.formatted_stats = JSON.stringify(data.stats, undefined, 4);

			var last_heard = pm.util.parseDate(data.last_heard);
			data.formatted_last_heard = last_heard.format(pm.util.date_formats.word);
			data.updated_age = moment().diff(last_heard, 'seconds');

			var start_time = pm.util.parseDate(data.start_time);
			data.formatted_start_time = start_time.format(pm.util.date_formats.word);
			data.uptime_string = pm.node.detail.uptimeString(start_time);

			data.formatted_score = data.score.toFixed(2);

			if (data.tags.runtimes && Object.keys(data.tags.runtimes).length > 0) {
				data.runtimes = [];
				for (var name in data.tags.runtimes) {
					data.runtimes.push({
						name: name,
						versions: data.tags.runtimes[name].join(', ')
					});
				}
			}

			return data;
		},

		switchTo: function() {
			var url_match = document.location.pathname.match(/\/(\d+)\/?$/);

			pm.leftmenu.redrawContainers();
			pm.node.list.updateNodeMenu(url_match[1]);

			pm.data.api({
				endpoint: 'node/' + url_match[1],
				callback: function(data) {
					var node = pm.node.detail.processNodeData(data.node);

					$('#main_right_view').html(Handlebars.templates.node_detail(node));
					pm.node.list.updateBreadcrumbs(data);

					pm.data.api({
						endpoint: 'node/' + url_match[1] + '/instances',
						callback: function(instance_data) {
							instance_data.instances.forEach(function(instance) {
								$('table.node-instances').append(Handlebars.templates.node_instance_row(instance));
							});

							// after rendering instances, set up expandable UUIDs
							// and add event handlers for viewing logs
							// TODO: this is shared with pm.version.js
							pm.widgets.uuid.update();
							$('.instance-log-container').each(function(i, element) {
									new pm.logs.instance(streamSocket, $(element).attr('data-instance'));
							});
						}
					});

					// Prettify some of the stats with pie charts
					if (node.stats.disk_total && node.stats.disk_free) {
						$.plot('.node-disk .chart', [
							{ label: "Disk used", color: "darkviolet", data: (node.stats.disk_total - node.stats.disk_free) },
							{ label: "Disk free", color: "lightblue", data: node.stats.disk_free }
						], { series: { pie: { show: true } }, legend: { container: '.node-disk .legend' } });
					}
					if (node.stats.mem_total && node.stats.mem_adjusted_free) {
						$.plot('.node-memory .chart', [
							{ label: "Memory used", color: "darksalmon", data: (node.stats.mem_total - node.stats.mem_adjusted_free) },
							{ label: "Memory free", color: "lightblue", data: node.stats.mem_adjusted_free }
						], { series: { pie: { show: true } }, legend: { container: '.node-memory .legend' } });
					}

					// Display a summary of jobs for this node
					pm.data.api({
						endpoint: 'job/list/node/' + url_match[1],
						callback: function(job_data) {
							pm.jobs.summary.show($('div.job-overview'), job_data.jobs.slice(0,10));

							$('div.job-overview a').on('click', function(e) {
								// when the user clicks on a job in the summary, provide extra data to the
								// job detail controller so it can render breadcrumbs to get back here
								e.preventDefault();
								e.stopPropagation();
								var state = { handle_in_js: true, node: data.node };
								window.history.pushState(state, '', $(e.target).attr('href'));
								pm.jobs.single.switchTo(state);
							});
						}
					});

					$('.loading-overlay').remove();
				}
			});
		}
	};
}());