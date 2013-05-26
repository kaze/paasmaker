define([
	'jquery',
	'underscore',
	'backbone',
	'moment',
], function($, _, Backbone, moment) {
	var module = {};

	module.dateFormats = {
		pacemaker: 'YYYY-MM-DD_HH:mm:ss.______ Z',
		word: 'MMMM Do YYYY, HH:mm:ss Z'
	};

	/**
	 * Parse a date string generated by the pacemaker in ISO-8601 format
	 * (which include microseconds but don't include the timezone, UTC),
	 * and return a moment.js object for arithmetic, formatting, etc.
	 */
	module.parseDate = function(dateString) {
		return moment(dateString + ' +0000', module.dateFormats.pacemaker);
	};

	module.shrinkUuids = function(scope) {
		$('code.uuid-shrink', scope).each(function(i, el) {
			el = $(el);
			el.text(el.attr('title').substr(0,8));
			el.on('click', module.shrinkClickHandler);
		});
	};

	module.shrinkClickHandler = function(e) {
		var el = $(e.target);
		if (el.text().length > 8) {
			el.text(el.attr('title').substr(0,8));
		} else {
			el.text(el.attr('title'));
		}
	};

	// number_format from: http://phpjs.org/functions/number_format/
	module.number_format = function(number, decimals, dec_point, thousands_sep) {
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

	return module;
});