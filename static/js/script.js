
var SimpleTagEditor = function(form, container)
{
	this.form = form;
	this.container = container;
	this.editarea = $('.editor', container);
	this.outputarea = $('.output', container);

	var _self = this;
	var addButton = $('<a href="#">Add...</a>');
	addButton.click(
		function(e)
		{
			var newRow = $('<div class="pair"></div>');
			newRow.append($('<input type="text" class="tag" />'));
			newRow.append($('<input type="text" class="value" />'));
			_self.editarea.append(newRow);
			_self.addRemoveButtons();

			e.preventDefault();
		}
	);

	this.container.append(addButton);
	/*var buildButton = $('<a href="#">Build...</a>');
	buildButton.click(function(e){_self.rebuildOutput()});
	this.container.append(buildButton);*/
	this.addRemoveButtons();

	// When the form is submitted, add our inputs.
	$(form).submit(
		function(e)
		{
			_self.rebuildOutput()
		}
	);
}

SimpleTagEditor.prototype.addRemoveButtons = function()
{
	// Find rows without a remove button.
	var rows = $('.pair', this.editarea).not('.has-remove');
	rows.each(
		function(index, element)
		{
			var el = $(element);
			var removeButton = $('<a href="#">Remove</a>');
			removeButton.click(
				function(e)
				{
					// Remove it from the DOM.
					el.remove();

					e.preventDefault();
				}
			);
			el.addClass('has-remove');
			el.append(removeButton);
		}
	);
}

SimpleTagEditor.prototype.rebuildOutput = function()
{
	var rows = $('.pair', this.editarea);
	this.outputarea.empty();
	var _self = this;
	rows.each(
		function(index, element)
		{
			var el = $(element);
			var tag = $('.tag', el).val();
			var value = $('.value', el).val();

			var tagEl = $('<input type="hidden" />');
			tagEl.attr({name: 'tags.' + tag, value: value});

			_self.outputarea.append(tagEl);
		}
	);
}

var FileUploader = function(container)
{
	this.container = container;

	this.upButton = $('<a href="#">Upload</a>');
	this.dropContainer = $('<div class="drop"></div>');

	this.dropContainer.append(this.upButton);
	this.container.append(this.dropContainer);

	this.statusArea = $('<div class="status"></div>');
	this.container.append(this.statusArea);
	this.progress = $('<progress value="0" max="100" />');
	this.container.append(this.progress);

	this.resumable = new Resumable(
		{
			target: '/files/upload',
			fileParameterName: 'file.data'
		}
	);

	this.resumable.assignBrowse(this.upButton);
	this.resumable.assignDrop(this.dropContainer);

	var _self = this;
	this.resumable.on('fileAdded', function(file){
		_self.statusArea.html(file.fileName + ', ' + file.size + ' bytes');
		_self.resumable.upload();
	});
	this.resumable.on('fileSuccess', function(file, message){
		// Parse the message.
		var contents = $.parseJSON(message);
		// Create a hidden form element with the uploaded identifier.
		var hiddenEl = $('<input type="hidden" name="uploaded_file" />');
		hiddenEl.attr('value', contents.data.identifier);
		_self.container.append(hiddenEl);
		_self.statusArea.html("Upload complete.");
		// Hide the drop container.
		_self.dropContainer.hide();
	});
	this.resumable.on('fileError', function(file, message){
		var contents = $.parseJSON(message);
		var errorList = $('<ul class="error"></ul>');
		for(var i = 0; i < contents.errors.length; i++)
		{
			var error = $('<li></li>');
			error.text(contents.errors[i]);
			errorList.append(error);
		}
		_self.statusArea.html(errorList);
	});
	this.resumable.on('progress', function(file){
		_self.progress.val(_self.resumable.progress() * 100);
	});
}

var JobRootStreamHandler = function()
{
	this.subscriptions = [];
	this.handlers = {};
	this.remote = null;
	this.connecting = false;
}

JobRootStreamHandler.prototype.subscribe = function(job_id, displayHandler)
{
	var _self = this;
	this.handlers[job_id] = displayHandler;
	if( !this.remote )
	{
		// We're not connected, so start connecting.
		this.connecting = true;
		this.remote = new WebSocket("ws://" + window.location.host + "/job/stream");
		this.remote.onopen = function() { _self.onopen(); };
		this.remote.onmessage = function (evt) { _self.onmessage(evt); };
	}

	if( this.connecting )
	{
		// Add it to the queue to be subscribed on startup.
		this.subscriptions.push(job_id);
	}
	else
	{
		// Subscribe!
		this.remote.send($.toJSON({request: 'subscribe', data: {'job_id': job_id}}));
	}
}

JobRootStreamHandler.prototype.onopen = function()
{
	// Mark us as connected.
	this.connecting = false;
	// Send through initial subscriptions.
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		this.subscribe(this.subscriptions[i], this.handlers[this.subscriptions[i]]);
	}
}

JobRootStreamHandler.prototype.onmessage = function (evt)
{
	// Parse the message.
	var message = $.parseJSON(evt.data);
	//console.log(message);

	switch(message.type)
	{
		case 'tree':
			var handler = this.handlers[message.data.job_id];
			handler.renderJobTree([message.data], 0);
			break;
		case 'subscribed':
			break;
		case 'status':
			var handler = this.handlers[message.data.root_id];
			handler.updateStatus(message.data);
			break;
		case 'new':
			var handler = this.handlers[message.data.root_id];
			handler.newJob(message.data);
			break;
	}
}

var LogRootStreamHandler = function()
{
	this.subscriptions = [];
	this.handlers = {};
	this.remote = null;
	this.connecting = false;
}

LogRootStreamHandler.prototype.isSubscribed = function(job_id)
{
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		if( this.subscriptions[i] == job_id )
		{
			return true;
		}
	}

	return false;
}

LogRootStreamHandler.prototype.subscribe = function(job_id, displayHandler, position, startup)
{
	var _self = this;
	this.handlers[job_id] = displayHandler;
	if( !this.remote )
	{
		// We're not connected, so start connecting.
		this.connecting = true;
		this.remote = new WebSocket("ws://" + window.location.host + "/log/stream");
		this.remote.onopen = function() { _self.onopen(); };
		this.remote.onmessage = function (evt) { _self.onmessage(evt); };
	}

	if( this.connecting )
	{
		// Add it to the queue to be subscribed on startup.
		if( !this.isSubscribed(job_id) )
		{
			this.subscriptions.push(job_id);
		}
	}
	else
	{
		if( !this.isSubscribed(job_id) || startup )
		{
			if( !this.isSubscribed(job_id) )
			{
				this.subscriptions.push(job_id);
			}

			// Subscribe!
			if( !position )
			{
				position = 0;
			}
			this.remote.send($.toJSON({request: 'subscribe', data: {'job_id': job_id, 'position': position}}));
		}
	}
}

LogRootStreamHandler.prototype.unsubscribe = function(job_id)
{
	// Remove from subscriptions.
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		if( this.subscriptions[i] == job_id )
		{
			this.subscriptions.splice(i, 1);
			break;
		}
	}

	if( !this.connecting )
	{
		// It's connected, so send unsubscribe.
		this.remote.send($.toJSON({request: 'unsubscribe', data: {'job_id': job_id}}));
	}
}

LogRootStreamHandler.prototype.onopen = function()
{
	// Mark us as connected.
	this.connecting = false;
	// Send through initial subscriptions.
	for( var i = 0; i < this.subscriptions.length; i++ )
	{
		this.subscribe(this.subscriptions[i], this.handlers[this.subscriptions[i]], 0, true);
	}
}

LogRootStreamHandler.prototype.onmessage = function (evt)
{
	// Parse the message.
	var message = $.parseJSON(evt.data);
	//console.log(message);

	// Find a handler to work with it.
	var handler = this.handlers[message.data.job_id];

	switch(message.type)
	{
		case 'lines':
			handler.handleNewLines(message.data);
			break;
		case 'zerosize':
			handler.handleZeroSizeLog(message.data);
			break;
	}
}

var JobDisplayHandler = function(container, jobStream, logStream)
{
	this.container = container;
	this.jobStream = jobStream;
	this.logStream = logStream;
	this.job_id = container.attr('data-job');

	this.jobStream.subscribe(this.job_id, this);
}

JobDisplayHandler.prototype.handleZeroSizeLog = function(message)
{
	var container = $('.' + message.job_id + ' .log');
	container.html("No log entries for this job.")
	container.addClass('no-data');
}

JobDisplayHandler.prototype.handleNewLines = function(message)
{
	var container = $('.' + message.job_id + ' .log');
	container.removeClass('no-data');
	var formatted = this.formatLogLines(message.lines.join(''));
	container.append(formatted);
	container.attr('data-position', message.position);
}

LOG_LEVEL_MAP = [
	['DEBUG', 'label'],
	['INFO', 'label label-info'],
	['WARNING', 'label label-warning'],
	['ERROR', 'label label-important'],
	['CRITICAL', 'label label-important']
]

JobDisplayHandler.prototype.formatLogLines = function(lines)
{
	var output = lines;
	output = htmlEscape(output);
	for( var i = 0; i < LOG_LEVEL_MAP.length; i++ )
	{
		output = output.replace(
			new RegExp('\\s' + LOG_LEVEL_MAP[i][0] + '\\s', 'g'),
			' <span class="' + LOG_LEVEL_MAP[i][1] + '">' + LOG_LEVEL_MAP[i][0] + '</span> '
		);
	}
	return output;
}

JobDisplayHandler.prototype.renderJobTree = function(tree, level, container)
{
	// Empty out the container.
	var workingContainer = this.container;
	if( container )
	{
		workingContainer = container;
	}
	workingContainer.empty();

	// Sort my tree by time.
	tree.sort(function(a, b) {
		return a.time - b.time;
	});

	var _self = this;
	$.each(tree, function(index, element)
	{
		var thisContainer = _self.createContainer(element.job_id, level, element);
		workingContainer.append(thisContainer);
	});
}

JobDisplayHandler.prototype.newJob = function(data)
{
	// Find the parent container.
	var parentId = data['parent_id'];
	var parentChildContainer = $('.children-' + parentId, this.container);
	var levelParent = parseInt(parentChildContainer.parent().attr('data-level'), 10) + 1;
	var newJobContainer = this.createContainer(data.job_id, levelParent, data);
	parentChildContainer.append(newJobContainer);
}

JobDisplayHandler.prototype.createContainer = function(job_id, level, data)
{
	var thisJobContainer = $('<div class="job-status level' + level + '"></div>');
	thisJobContainer.attr('data-level', level);

	var details = $('<div class="details clearfix"></div>');
	details.addClass(job_id);
	details.append($('<span class="state"></span>'));
	details.append($('<span class="toolbox"></span>'));
	details.append($('<span class="title"></span>'));
	details.append($('<span class="summary"></span>'));
	details.append($('<span class="time"></span>'));
	details.append($('<pre class="log"></pre>'));
	thisJobContainer.append(details);

	var childrenContainer = $('<div class="children"></div>');
	childrenContainer.addClass('children-' + job_id);
	thisJobContainer.append(childrenContainer);

	$('.title', thisJobContainer).text(data.title);
	if( data.summary && data.state != 'SUCCESS' )
	{
		$('.summary', thisJobContainer).text('Summary: ' + data.summary);
	}
	else
	{
		$('.summary', thisJobContainer).text('');
	}

	/*var thisTime = new Date();
	thisTime.setTime(data.time * 1000);
	$('.time', thisJobContainer).text(thisTime.toString());*/

	var stateContainer = $('.state', thisJobContainer);
	this.setStateClass(stateContainer, data.state);
	this.setStateIcon(stateContainer, data.state);
	var logContainer = $('.log', thisJobContainer);

	var toolbox = $('.toolbox', thisJobContainer);
	var _self = this;
	if( false == toolbox.hasClass('populated') )
	{
		// Populate and hook up the toolbox.
		var logExpander = $('<a href="#" title="View log for this job"><i class="icon-list"></i></a>');
		logExpander.click(
			function(e)
			{
				_self.toggleSubscribeLog(data.job_id, logContainer);

				e.preventDefault();
			}
		);
		toolbox.append(logExpander);
		toolbox.addClass('populated');
	}

	// Recurse into the children.
	if( data.children )
	{
		var childContainer = $('.children', thisJobContainer);
		_self.renderJobTree(data.children, level + 1, childContainer);
	}

	return thisJobContainer;
}

BOOTSTRAP_CLASS_MAP = {
	'FAILED': 'important', // Er, ok.
	'ABORTED': 'warning',
	'SUCCESS': 'success',
	'WAITING': 'info',
	'RUNNING': 'primary'
}

BOOTSTRAP_ICON_MAP = {
	'FAILED': 'icon-remove',
	'ABORTED': 'icon-ban-circle',
	'SUCCESS': 'icon-ok',
	'WAITING': 'icon-time',
	'RUNNING': 'icon-random',
	'NEW': 'icon-certificate'
}

JobDisplayHandler.prototype.setStateClass = function(element, state)
{
	var oldState = element.attr('data-state');
	if( oldState )
	{
		element.removeClass('state-' + oldState);
		var oldBootstrapClass = BOOTSTRAP_CLASS_MAP[oldState];
		if( oldBootstrapClass )
		{
			element.removeClass('label-' + oldBootstrapClass);
		}
	}
	element.addClass('state-' + state);
	element.attr('data-state', state);

	// And add a class that inherits a bootstrap colour.
	var bootstrapClass = BOOTSTRAP_CLASS_MAP[state];
	if( !bootstrapClass )
	{
		bootstrapClass = 'default';
	}

	element.addClass('label');
	element.addClass('label-' + bootstrapClass);
}

JobDisplayHandler.prototype.setStateIcon = function(element, state)
{
	var icon = $('<i></i>');
	icon.addClass('icon-white');
	icon.addClass(BOOTSTRAP_ICON_MAP[state]);

	element.html(icon);
	var textual = $('<span></span>');
	textual.text(state);
	element.append(textual);
}

JobDisplayHandler.prototype.updateStatus = function(status)
{
	// Find the appropriate status element.
	var el = $('.' + status.job_id + ' .state', this.container);
	el.text(status.state);
	this.setStateClass($('.state', this.container), status.state);
	this.setStateIcon($('.state', this.container), status.state);

	if( status.summary && status.state != 'SUCCESS' )
	{
		var summaryEl = $('.' + status.job_id + ' .summary', this.container);
		summaryEl.text('Summary: ' + status.summary);
	}
}

JobDisplayHandler.prototype.toggleSubscribeLog = function(job_id, container)
{
	if( this.logStream.isSubscribed(job_id) )
	{
		container.slideUp();
		this.logStream.unsubscribe(job_id);
	}
	else
	{
		var position = container.attr('data-position');
		this.logStream.subscribe(job_id, this, position);
		container.slideDown();
	}
}

var RouterStatsStreamHandler = function(container)
{
	this.container = container;
	this.input_name = container.attr('data-name');
	this.input_id = container.attr('data-inputid');

	var _self = this;
	this.ready = false;
	this.routerStatsRemote = new WebSocket("ws://" + window.location.host + "/router/stats/stream");
	this.routerStatsRemote.onopen = function() {
		// It will send us a ready message when we can start.
	};
	this.routerStatsRemote.onmessage = function (evt) {
		var message = $.parseJSON(evt.data);
		//console.log(message);
		switch(message.type)
		{
			case 'update':
				_self.showUpdate(message.data);
				break;
			case 'history':
				_self.showGraph(message.data);
				break;
			case 'ready':
				this.ready = true;
				// Start updating.
				_self.requestUpdate();
				if( _self.isGraphing )
				{
					_self.requestGraph();
				}
				break;
		}
	};

	// For speed later, pre-lookup the value instances.
	this.requests = $('.stat-requests .value', container);
	this.bytes = $('.stat-bytes .value', container);
	this.time_average = $('.stat-time_average .value', container);
	this.onexx = $('.stat-1xx .value', container);
	this.twoxx = $('.stat-2xx .value', container);
	this.threexx = $('.stat-3xx .value', container);
	this.fourxx = $('.stat-4xx .value', container);
	this.fivexx = $('.stat-5xx .value', container);

	this.onexx_percentage = $('.stat-1xx_percentage .value', container);
	this.twoxx_percentage = $('.stat-2xx_percentage .value', container);
	this.threexx_percentage = $('.stat-3xx_percentage .value', container);
	this.fourxx_percentage = $('.stat-4xx_percentage .value', container);
	this.fivexx_percentage = $('.stat-5xx_percentage .value', container);
	this.nginxtime_average = $('.stat-nginxtime_average .value', container);

	// Hook up the show more/less button.
	var showButton = $('.show-all', container);
	var secondary = $('.secondary', container);
	showButton.click(
		function(e)
		{
			if( secondary.is(':visible') )
			{
				showButton.text('Show all');
			}
			else
			{
				showButton.text('Hide');
			}
			secondary.slideToggle();
		}
	);

	var graphButton = $('.show-graph', container);
	this.graphArea = $('.graph', container);
	this.isGraphing = false;
	graphButton.click(
		function(e)
		{
			_self.graphArea.toggle();
			_self.isGraphing = !_self.isGraphing;
			_self.setupGraphArea();
			_self.requestGraph();
		}
	);

	// If the graph area is visible on page load,
	// start graphing now.
	if( this.graphArea.is(':visible') )
	{
		this.setupGraphArea();
		// Don't make the first call to update the graph,
		// because it's likely not ready yet.
		this.isGraphing = true;
	}
}

RouterStatsStreamHandler.prototype.setupGraphArea = function()
{
	var options = {
		series: { shadowSize: 1, bars: { show: true, fill: true, barWidth: 1000 } },
		yaxis: { min: 0 },
		xaxis: { mode: "time", minTickSize: [30, "second"], }
	};
	this.plot = $.plot(this.graphArea, [], options);
}

RouterStatsStreamHandler.prototype.requestUpdate = function()
{
	this.routerStatsRemote.send($.toJSON({request: 'update', data: {'name': this.input_name, 'input_id': this.input_id}}));
}

RouterStatsStreamHandler.prototype.requestGraph = function()
{
	var now = new Date();
	// TODO: Allow more configuration, less assumptions.
	this.routerStatsRemote.send(
		$.toJSON(
			{
				request: 'history',
				data: {
					'name': this.input_name,
					'input_id': this.input_id,
					'metric': 'requests',
					'start': (now.getTime() / 1000) - 60
				}
			}
		)
	);
}

RouterStatsStreamHandler.prototype.displayIncludingLast = function(key, values, container)
{
	var value = '';
	value += number_format(values[key]);

	if( this.lastNumbers )
	{
		var difference = values[key] - this.lastNumbers[key];

		value += ' - <span class="diff">' + number_format(difference) + '/s</span>';
	}

	container.html(value);
}

RouterStatsStreamHandler.prototype.showUpdate = function(update)
{
	this.displayIncludingLast('requests', update, this.requests);
	this.displayIncludingLast('bytes', update, this.bytes);
	this.time_average.text(number_format(update.time_average));

	this.displayIncludingLast('1xx', update, this.onexx);
	this.displayIncludingLast('2xx', update, this.twoxx);
	this.displayIncludingLast('3xx', update, this.threexx);
	this.displayIncludingLast('4xx', update, this.fourxx);
	this.displayIncludingLast('5xx', update, this.fivexx);

	this.onexx_percentage.text(toFixed(update['1xx_percentage'], 2) + '%');
	this.twoxx_percentage.text(toFixed(update['2xx_percentage'], 2) + '%');
	this.threexx_percentage.text(toFixed(update['3xx_percentage'], 2) + '%');
	this.fourxx_percentage.text(toFixed(update['4xx_percentage'], 2) + '%');
	this.fivexx_percentage.text(toFixed(update['5xx_percentage'], 2) + '%');
	this.nginxtime_average.text(number_format(update.nginxtime_average));

	// And then in 1s, request it again.
	var _self = this;
	setTimeout(function(){ _self.requestUpdate(); }, 1000);

	this.lastNumbers = update;
}

RouterStatsStreamHandler.prototype.showGraph = function(graphdata)
{
	//console.log(graphdata.points);
	var graphPoints = graphdata.points;
	if( graphPoints.length == 0 )
	{
		// No data returned. Fake it!
		graphPoints.push([graphdata.start, 0]);
		graphPoints.push([graphdata.end, 0]);
	}
	else
	{
		if( graphPoints[0][0] != graphdata.start )
		{
			// Doesn't start with the start time. Insert
			// a point to make it make sense.
			graphPoints.splice(0, 0, [graphdata.start, 0])
		}
		if( graphPoints[graphPoints.length - 1][0] != graphdata.end )
		{
			// Doesn't end with the end time. Insert a
			// point to make it make sense.
			graphPoints.push([graphdata.end, 0])
		}
	}

	// Now convert all the times to unix timestamp milliseconds.
	for( var i = 0; i < graphPoints.length; i++ )
	{
		graphPoints[i][0] *= 1000;
	}

	//console.log(graphPoints);

	this.plot.setData([graphPoints]);
	this.plot.setupGrid();
	this.plot.draw();

	// And then in 1s, request it again.
	if( this.isGraphing )
	{
		var _self = this;
		setTimeout(function(){ _self.requestGraph(); }, 1000);
	}
}

function testBrowserFeatures(resultContainer)
{
	resultContainer.empty();

	resultList = $('<ul></ul>');

	var reportResult = function(name, result)
	{
		resultLabel = result ? 'Success' : 'Failure';
		resultList.append($('<li>' + name + ': ' + resultLabel + '</li>'));
	}

	reportResult("Websockets", Modernizr.websockets);

	var r = new Resumable();

	reportResult("HTML5 File uploads", r.support);

	resultContainer.append(resultList);
}

$(document).ready(
	function()
	{
		if( $('.workspace-tag-editor').length > 0 )
		{
			var workspaceTagEditor = new SimpleTagEditor($('form'), $('.workspace-tag-editor'));
		}

		if( $('.test-browser-features').length > 0 )
		{
			testBrowserFeatures($('.test-browser-features'));
		}

		if( $('.file-uploader-widget').length > 0 )
		{
			$('.file-uploader-widget').each(
				function(index, element)
				{
					var uploader = new FileUploader($(element));
				}
			);
		}

		var jobStream = new JobRootStreamHandler();
		var logStream = new LogRootStreamHandler();
		if( $('.job-root').length > 0 )
		{
			$('.job-root').each(
				function(index, element)
				{
					var jobDisplay = new JobDisplayHandler($(element), jobStream, logStream);
				}
			);
		}

		if( $('.router-stats').length > 0 )
		{
			$('.router-stats').each(
				function(index, element)
				{
					var routerStats = new RouterStatsStreamHandler($(element));
				}
			);
		}

		// Disable any disabled buttons.
		$('.btn.disabled').click(
			function(e)
			{
				e.preventDefault();
			}
		);

		// Populate the workspaces dropdown.
		// TODO: Make this more efficient without having the server include it in the HTML.
		// NOTE: This doesn't handle errors - if you're not logged in, no list.
		var workspaceListContainer = $('.nav .workspace-list');
		if( workspaceListContainer.length > 0 )
		{
			$.getJSON(
				'/workspace/list?format=json',
				function(data, text, xhr)
				{
					for( var i = 0; i < data.data.workspaces.length; i++ )
					{
						workspace = data.data.workspaces[i];
						thisA = $('<a href="/workspace/' + workspace.id + '/applications"></a>');
						thisA.text(workspace.name);
						thisLi = $('<li></li>');
						thisLi.append(thisA);
						workspaceListContainer.append(thisLi);
					}
				}
			);
		}

		// On the new applications page, collapse the options until you click one.
		var scms = $('.scm-container');
		if( scms.length > 0 )
		{
			$('.scm', scms).not('.scm-active').each(
				function(index, element)
				{
					var el = $(element);
					var inner = $('.inner', el);
					inner.hide();
					var show = $('<a href="#"><i class="icon-plus-sign"></i> Show...</a>');
					show.click(
						function(e)
						{
							inner.show();
							show.hide();
							e.preventDefault();
						}
					);
					el.append(show);
				}
			);

			$('.scm-list').each(
				function(index, element)
				{
					var el = $(element);
					var plugin = el.attr('data-plugin');
					$.getJSON(
						'/scm/list/repos?plugin=' + escape(plugin),
						function(data, text, xhr)
						{
							el.empty();
							el.append($('<option value="">Select...</option>'));
							for(var i = 0; i < data.data.repositories.length; i++ )
							{
								var entry = data.data.repositories[i];
								var op = $('<option></option>');
								op.text(entry.title);
								op.val(entry.url);

								el.append(op);
							}
						}
					);
					el.change(
						function(e)
						{
							// TODO: This assumes a lot about the HTML.
							var inner = el.parent();
							var location = $('input.lister-target', $(inner));
							location.val(el.val());
						}
					);
				}
			);
		}
	}
)

// Helper functions.
// number_format from: http://phpjs.org/functions/number_format/
function number_format (number, decimals, dec_point, thousands_sep) {
  number = (number + '').replace(/[^0-9+\-Ee.]/g, '');
  var n = !isFinite(+number) ? 0 : +number,
    prec = !isFinite(+decimals) ? 0 : Math.abs(decimals),
    sep = (typeof thousands_sep === 'undefined') ? ',' : thousands_sep,
    dec = (typeof dec_point === 'undefined') ? '.' : dec_point,
    s = '',
    toFixedFix = function (n, prec) {
      var k = Math.pow(10, prec);
      return '' + Math.round(n * k) / k;
    };
  // Fix for IE parseFloat(0.55).toFixed(0) = 0;
  s = (prec ? toFixedFix(n, prec) : '' + Math.round(n)).split('.');
  if (s[0].length > 3) {
    s[0] = s[0].replace(/\B(?=(?:\d{3})+(?!\d))/g, sep);
  }
  if ((s[1] || '').length < prec) {
    s[1] = s[1] || '';
    s[1] += new Array(prec - s[1].length + 1).join('0');
  }
  return s.join(dec);
}

// From: http://stackoverflow.com/questions/661562/how-to-format-a-float-in-javascript
function toFixed(value, precision) {
    var power = Math.pow(10, precision || 0);
    return (Math.round(value * power) / power).toFixed(precision);
}

// From: http://stackoverflow.com/questions/1219860/javascript-jquery-html-encoding
// TODO: Reconsider if this is appropriate.
function htmlEscape(str) {
    return String(str)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
}