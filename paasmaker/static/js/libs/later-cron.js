if (!Array.prototype.indexOf) {
    Array.prototype.indexOf = function (searchElement /*, fromIndex */ ) {
        "use strict";
        if (this == null) {
            throw new TypeError();
        }
        var t = Object(this);
        var len = t.length >>> 0;
        if (len === 0) {
            return -1;
        }
        var n = 0;
        if (arguments.length > 1) {
            n = Number(arguments[1]);
            if (n != n) { // shortcut for verifying if it's NaN
                n = 0;
            } else if (n != 0 && n != Infinity && n != -Infinity) {
                n = (n > 0 || -1) * Math.floor(Math.abs(n));
            }
        }
        if (n >= len) {
            return -1;
        }
        var k = n >= 0 ? n : Math.max(len - Math.abs(n), 0);
        for (; k < len; k++) {
            if (k in t && t[k] === searchElement) {
                return k;
            }
        }
        return -1;
    }
}

if(!String.prototype.trim) {
  String.prototype.trim = function () {
    return this.replace(/^\s+|\s+$/g,'');
  };
}/**
* Later.js 0.0.1
* (c) 2012 Bill, BunKat LLC.
* Later is freely distributable under the MIT license.
* For all details and documentation:
*     http://bunkat.github.com/later
*/
(function() {

    "use strict";

    /**
    * Calculates the next occurrence (or occcurrences) of a given schedule.
    * Schedules are simply a set of constraints that must be met for a 
    * particular date to be valid. Schedules can be generated using Recur or
    * can be created directly.  
    *
    * Schedules have the following form:
    *
    * {
    *   schedules: [
    *       {
    *           constraintId: [valid values],
    *           constraintId: [valid values],
    *           ...
    *       },
    *       {
    *           constraintId: [valid values],
    *           constraintId: [valid values],
    *           ...
    *       }
    *       ...
    *   ],
    *   exceptions: [
    *       {
    *           constraintId: [valid values],
    *           constraintId: [valid values],
    *           ...         
    *       },
    *       {
    *           constraintId: [valid values],
    *           constraintId: [valid values],
    *           ...         
    *       },
    *       ...
    *   ]   
    * }
    *
    * See Recur.js for the available constraints and their value ranges.  May
    * also be useful to create a schedule using Recur and then examining the
    * schedule that is produced.
    */

    /**
    * Initializes the Later object. 
    *
    * @param {Int} resolution: Minimum number of seconds between occurrences
    * @param {Bool} useLocalTime: True if local time zone should be used
    * @api public
    */
    var Later = function(resolution, useLocalTime) {

        var isLocal = useLocalTime || false,
            get = 'get' + (isLocal ? '' : 'UTC'),
            exec = true,

            // constants
            SEC = 1000,
            MIN = SEC * 60,
            HOUR = MIN * 60,
            DAY = HOUR * 24,

            // aliases for common math functions
            ceil = Math.ceil,
            floor = Math.floor,
            max = Math.max,

            // data prototypes to switch between UTC and local time calculations
            dateProto = Date.prototype,
            getYear = dateProto[get + 'FullYear'],
            getMonth = dateProto[get + 'Month'],
            getDate = dateProto[get + 'Date'],
            getDay = dateProto[get + 'Day'],
            getHour = dateProto[get + 'Hours'],
            getMin = dateProto[get + 'Minutes'],
            getSec = dateProto[get + 'Seconds'];

        // minimum time between valid occurrences in seconds
        resolution = resolution || 1;

        /**
        * Finds the next valid value which is either the next largest valid
        * value or the minimum valid value if no larger value exists. To
        * simplify some calculations, the min value is then added to a specified
        * offset.  
        * 
        * For example, if the current minute is 5 and the next valid 
        * value is 1, the offset will be set to 60 (max number of minutes) and
        * nextInRange will return 61. This is the number of minutes that must
        * be added to the current hour to get to the next valid minute.
        *
        * @param {Int/String} val: The current value
        * @param {[]} values: Array of possible valid values
        * @param {Int/String} minOffset: Value to add to the minimum value
        */
        var nextInRange = function(val, values, minOffset) {
            var cur, next = null, min = values[0], i = values.length;
            while (i--) {
                cur = values[i];
                if (cur === val) {
                    return val;
                }

                min = cur < min ? cur : min;
                next = cur > val && (!next || cur < next) ? cur : next;
            }

            return next || (minOffset === undefined ? min : (min + minOffset));
        };

        /**
        * Finds the previous valid value which is either the next smallest valid
        * value or the maximum valid value if no smaller value exists. To
        * simplify some calculations, the min value is then substracted to a specified
        * offset.  
        * 
        * For example, if the current minute is 5 and the next valid 
        * value is 7, the offset will be set to 60 (max number of minutes) and
        * prevInRange will return -67. This is the number of minutes that must
        * be added to the current hour to get to the next valid minute.
        *
        * @param {Int/String} val: The current value
        * @param {[]} values: Array of possible valid values
        * @param {Int/String} maxOffset: Value to subtract from the maximum value
        */
        var prevInRange = function(val, values, maxOffset) {
            var cur, prev = null, i = values.length, max = values[i-1];
            while (i--) {
                cur = values[i];
                if (cur === val) {
                    return val;
                }

                max = cur > max ? cur : max;
                prev = cur < val && (!prev || cur > prev) ? cur : prev;
            }

            return prev !== null ? prev : (maxOffset === undefined ? max : (max - maxOffset));
        };

        /**
        * Builds and returns a new Date using the specified values.  Date
        * returned is either using Local time or UTC based on isLocal. 
        *
        * @param {Int} yr: Four digit year
        * @param {Int} mt: Month between 0 and 11, defaults to 0
        * @param {Int} dt: Date between 1 and 31, defaults to 1
        * @param {Int} hr: Hour between 0 and 23, defaults to 0
        * @param {Int} mn: Minute between 0 and 59, defaults to 0
        * @param {Int} sc: Second between 0 and 59, defaults to 0
        */
        var nextDate = function(yr, mt, dt, hr, mn, sc) {
            mt = mt === undefined ? 0 : mt;
            dt = dt === undefined ? 1 : dt;
            hr = hr === undefined ? 0 : hr;
            mn = mn === undefined ? 0 : mn;
            sc = sc === undefined ? 0 : sc;

            return isLocal ? new Date(yr, mt, dt, hr, mn, sc) :
                new Date(Date.UTC(yr, mt, dt, hr, mn, sc));
        };

        /**
        * Builds and returns a new Date using the specified values.  Date
        * returned is either using Local time or UTC based on isLocal. 
        *
        * @param {Int} yr: Four digit year
        * @param {Int} mt: Month between 0 and 11, defaults to 11
        * @param {Int} dt: Date between 1 and 31, defaults to last day of month
        * @param {Int} hr: Hour between 0 and 23, defaults to 23
        * @param {Int} mn: Minute between 0 and 59, defaults to 59
        * @param {Int} sc: Second between 0 and 59, defaults to 59
        */
        var prevDate = function(yr, mt, dt, hr, mn, sc) {
            mt = mt === undefined ? 11 : mt;
            dt = dt === undefined ? getDate.call(nextDate(yr, mt+1, 0)) : dt;
            hr = hr === undefined ? 23 : hr;
            mn = mn === undefined ? 59 : mn;
            sc = sc === undefined ? 59 : sc;

            return isLocal ? new Date(yr, mt, dt, hr, mn, sc) :
                new Date(Date.UTC(yr, mt, dt, hr, mn, sc));
        };

        /**
        * Pads a digit with a leading zero if it is less than 10.
        *
        * @param {Int} val: The value that needs to be padded
        */
        var pad = function(val) {
            return (val < 10 ? '0' : '') + val;
        };

        /**
        * Calculates the next valid occurrence of a particular schedule that 
        * occurs on or after the specified start time. 
        *
        * @param {object} schedule: Valid schedule object containing constraints
        * @param {Date} start: The first possible valid occurrence
        * @param {Date} end: The last possible valid occurrence
        * @param {boolean} reverse: True if we are looking for previous occurrences
        */
        var getNextForSchedule = function(sched, start, end, reverse) {
            var next, inc, x, cur,
                Y, M, D, d, h, m, s,
                oJan1, oMonthStart, oWeekStart, oWeekStartY, oMonthEnd,
                oDec31,
                t, dy, wy, wm, dc,
                daysInYear, daysInMonth, firstDayOfMonth,
                weekStart, weeksInYear, weeksInMonth,
                maxLoopCount = 1000;

            var range = reverse ? prevInRange : nextInRange,
                date = reverse ? prevDate : nextDate;

            // handle any after constraints
            // after constraints are not applied when searching backwards
            next = reverse ? start : after(start, sched);

            // It's not pretty, but just keep looping through all of the
            // constraints until they have all been met (or no valid 
            // occurrence exists). All calculations are done just in time and 
            // and only once to prevent extra work from being done each loop.
            while (next && maxLoopCount--) {

                // make sure we are still with in the boundaries
                if (end &&
                     ((!reverse && next.getTime() > end.getTime()) ||
                     (reverse && next.getTime() < end.getTime()))) {
                    return null;
                }

                // check year
                Y = getYear.call(next);
                if (sched.Y && (inc = range(Y, sched.Y, 0)) !== Y ) {
                    next = (!reverse && inc > Y) || (reverse && inc < Y) ? date(inc) : null;
                    continue;
                }

                // check day of year (one based)
                oJan1 = nextDate(Y, 0, 1);
                oDec31 = nextDate(Y + 1, 0, 0);
                if (sched.dy) {
                    dy = ceil((next.getTime() - oJan1.getTime() + 1)/DAY);
                    daysInYear = ceil((oDec31.getTime() - oJan1.getTime() + 1)/DAY);

                    if (((inc = range(dy, sched.dy, daysInYear)) || daysInYear) !== dy) {
                        next = date(Y, 0, inc);
                        continue;
                    }
                }

                // check month (one based)
                M = getMonth.call(next);
                if (sched.M && (inc = range(M+1, sched.M, 12)) !== M+1) {
                    next = date(Y, inc-1);
                    continue;
                }

                // check week of year (one based, ISO week)
                D = getDate.call(next);
                d = getDay.call(next);
                if (sched.wy) {
                    oWeekStart = date(Y, M, D + 4 - (d || 7));
                    oWeekStartY = date(getYear.call(oWeekStart),0,1);
                    weeksInYear = getDay.call(oJan1) === 4 ||
                        getDay.call(oDec31) === 4 ? 53 : 52;

                    wy = ceil((((oWeekStart.getTime()-oWeekStartY.getTime())/DAY)+1)/7);
                    if (((inc = range(wy, sched.wy, weeksInYear)) || weeksInYear) !== wy) {
                        if(inc < 0) inc += 1; // don't double count a week when reverse

                        next = date(
                                getYear.call(oWeekStart),
                                getMonth.call(oWeekStart),
                                getDate.call(oWeekStart) - 3 + (inc - wy) * 7 +
                                (reverse ?  6 : 0)); // head to end of week if reverse
                        continue;
                    }
                }

                // check date of month (one based)
                oMonthEnd = nextDate(Y, M + 1, 0);
                daysInMonth = getDate.call(oMonthEnd);
                if (sched.D && ((inc = range(D, sched.D, daysInMonth)) || daysInMonth) !== D) {
                    // if we are going backwards, just jump to the last day in
                    // the previous month to avoid errors in calculating diff to
                    // desired date
                    next = date(Y, M, inc < 0 ? 0 : inc);
                    continue;
                }

                // check week of month (one based, 0 for last week of month)
                if (sched.wm) {
                    firstDayOfMonth = getDay.call(nextDate(Y, M, 1));
                    wm = floor((((D + firstDayOfMonth - 1)/7))+1);
                    weeksInMonth = floor((((daysInMonth + firstDayOfMonth - 1)/7))+1);
                    if (((inc = range(wm, sched.wm, weeksInMonth)) || weeksInMonth) !== wm) {
                        // jump to the Sunday of the desired week, making sure not
                        // to double count the last week in the month if we cross
                        // a month boundary, set to 1st of month for week 1
                        if(inc === 0) { //only happens in reverse, go to end of prev month
                            next = date(Y, M, inc);
                        }
                        else {
                            next = date(Y, M,
                                (inc < 0 ? inc+1 : inc-1) * 7 - (firstDayOfMonth - 1) -
                                (inc > weeksInMonth && getDay.call(oMonthEnd) < 6 ? 7 : 0) +
                                (inc === weeksInMonth + 1 ? getDay.call(oMonthEnd) + 1 : 0) +
                                (reverse ? 6 : 0)); // skip to end of week in reverse
                        }
                        continue;
                    }
                }

                // check day of week (zero based)
                if (sched.d && (inc = range(d+1, sched.d, 7)) !== d+1) {
                    next = date(Y, M, D + (inc-1) - d);
                    continue;
                }

                // check day of week count (one based, 0 for last instance)
                if (sched.dc) {
                    dc = floor((D - 1) / 7) + 1;
                    if ((inc = range(dc, sched.dc, 0)) !== dc) {
                        if (reverse) {
                            if (inc > 0) {
                                next = date(Y, M + (inc < dc ? 0 : -1), 7 + (7 * (inc-1)));
                                continue;
                            }
                            else if (inc === 0 && D < (daysInMonth - 6)) {
                                next = date(Y, M, inc);
                                continue;
                            }
                        }
                        else {
                            if (inc > 0) {
                                next = date(Y, M + (inc < dc ? 1 : 0), 1 + (7 * (inc-1)));
                                continue;
                            }
                            else if (inc < 1 && D < (daysInMonth - 6)) {
                                next = date(Y, M, daysInMonth - 6);
                                continue;
                            }
                        }
                    }
                }

                // check hour of day (zero based)
                h = getHour.call(next);
                if (sched.h && (inc = range(h, sched.h, 24)) !== h) {
                    next = date(Y, M, D, inc);
                    continue;
                }

                // check minute of hour (zero based)
                m = getMin.call(next);
                if (sched.m && (inc = range(m, sched.m, 60)) !== m) {
                    next = date(Y, M, D, h, inc);
                    continue;
                }

                // check second of minute (zero based)
                s = getSec.call(next);
                if (sched.s && (inc = range(s, sched.s, 60)) !== s) {
                    next = date(Y, M, D, h, m, inc);
                    continue;
                }

                // check time of day (24-hr)
                if (sched.t) {
                    t = pad(h) +':'+ pad(m) +':'+ pad(s);
                    if ((inc = range(t, sched.t)) !== t) {
                        x = inc.split(':');
                        var dayInc = !reverse ? (t > inc ? 1 : 0) : (t < inc ? -1 : 0);
                        next = date(Y, M, D + dayInc, x[0], x[1], x[2]);
                        continue;
                    }
                }

                // if we make it this far, all constraints have been met
                break;
            }

            return maxLoopCount > 0 ? next : null;
        };

        /**
        * Increments a date by a given amount of time.  Date
        * returned is either using Local time or UTC based on isLocal. 
        *
        * @param {Int} yr: Number of years to increment by
        * @param {Int} mt: Number of months to increment by
        * @param {Int} dt: Number of days to increment by
        * @param {Int} hr: Number of hours to increment by
        * @param {Int} mn: Number of minutes to increment by
        * @param {Int} sc: Number of seconds to increment by
        */
        var after = function (start, sched) {
            var yr = getYear.call(start) + getAfter(sched.aY),
                mt = getMonth.call(start) + getAfter(sched.aM),
                dt = getDate.call(start) +
                        max(getAfter(sched.aD), getAfter(sched.ady), getAfter(sched.ad),
                        getAfter(sched.awy) * 7, getAfter(sched.awm) * 7),
                hr = getHour.call(start) + getAfter(sched.ah),
                mn = getMin.call(start) + getAfter(sched.am),
                sc = getSec.call(start) + getAfter(sched.as);

            return nextDate(yr, mt, dt, hr, mn, sc);
        };

        /**
        * Returns the value of an after constraint or 0 if not set. 
        *
        * @param {Array} constraint: After constrant to check
        */
        var getAfter = function (constraint) {
            return constraint && constraint[0] ? constraint[0] : 0;
        };

        /**
        * Returns a new date object that represents the next possible valid
        * occurrence based on the resolution that has beeen configured.
        *
        * @param {Date} date: The Date object to be incremented
        * @param {Boolean} backwards: True to tick backwards instead of forwards
        */
        var tick = function (date, backwards) {
            return !backwards ?
                new Date(date.getTime() + (resolution * 1000)) :
                new Date(date.getTime() - (resolution * 1000)) ;
        };

        return {

            /**
            * Returns true if the specified date meets all of the constraints
            * defined within the specified schedule. 
            *
            * @param {Recur} recur: Set of schedule and exception constraints
            * @param {Date} date: The date to validate against
            * @api public
            */
            isValid: function (recur, date) {
                date.setMilliseconds(0);
                return date.getTime() === this.getNext(recur, date).getTime();
            },

            /**
            * Returns the next one or more valid occurrences of a schedule. 
            *
            * @param {Recur} recur: Set of schedule and exception constraints
            * @param {Int} count: The number of occurrences to return
            * @param {Date} startDate: The initial date to start looking from
            * @param {Date} endDate: The last date to include
            * @param {boolean} reverse: True to search for occurrences in reverse
            * @api public
            */
            get: function (recur, count, startDate, endDate, reverse) {
                var occurrences = [], date;

                while (count-- > 0 && (date =
                        !reverse ?
                            this.getNext(recur, date || startDate, endDate) :
                            this.getPrevious(recur, date || startDate, endDate)
                        )) {
                    occurrences.push(date);
                    date = tick(date, reverse);
                }

                return occurrences;
            },

            /**
            * Returns the next valid occurrence of a schedule. 
            *
            * @param {Recur} recur: Set of schedule and exception constraints
            * @param {Date} startDate: The initial date to start looking from
            * @param {Date} endDate: The last date to include
            * @api public
            */
            getNext: function (recur, startDate, endDate) {
                var schedules = recur.schedules || [],
                    exceptions = {schedules: recur.exceptions || []},
                    start = startDate || new Date(),
                    date, tDate,
                    i = schedules.length;

                // return null if we're past the specified end date
                if (endDate && startDate.getTime() > endDate.getTime()) {
                    return null;
                }

                while(i--) {
                    tDate = getNextForSchedule(schedules[i], start, endDate);
                    if (!date || (tDate < date)) {
                        date = tDate;
                    }
                }

                if (date && exceptions.schedules.length > 0 &&
                        this.isValid(exceptions, date)) {
                    date = this.getNext(recur, tick(date), endDate);
                }

                return date;
            },

            /**
            * Returns the previous valid occurrence of a schedule based on the
            * provided endDate. 
            *
            * @param {Recur} recur: Set of schedule and exception constraints
            * @param {Date} endDate: The date to start the search from
            * @param {Date} startDate: The last date to include in the search
            * @api public
            */
            getPrevious: function (recur, startDate, endDate) {
                var schedules = recur.schedules || [],
                    exceptions = {schedules: recur.exceptions || []},
                    end = startDate || new Date(),
                    date, tDate,
                    i = schedules.length;

                // return null if we're earlier than the specified endDate date
                if (endDate && startDate.getTime() < endDate.getTime()) {
                    return null;
                }

                while(i--) {
                    tDate = getNextForSchedule(schedules[i], end, endDate, true);
                    if (!date || (tDate > date)) {
                        date = tDate;
                    }
                }

                if (date && exceptions.schedules.length > 0 &&
                        this.isValid (exceptions, date)) {
                    date = this.getPrevious(recur, tick(date, true), endDate);
                }

                return date;
            },

            /**
            * Executes the provided callback on the provided recurrence 
            * schedule. Returns true if the timer was started.
            *
            * @param {Recur} recur: Set of schedule and exception constraints
            * @param {Date} startDate: The initial date to start looking from
            * @param {Func} callback: The function to execute
            * @param {arg[]} arg: Argument or array of arguments to pass to the
            *                     callback
            * @api public
            */
            exec: function (recur, startDate, callback, arg) {
                var next = this.getNext(recur, tick(startDate));

                if (next) {
                    next = next.getTime() - (new Date()).getTime();

                    // reschedule the exec if the delay is greater than 2^31-1 
                    // otherwise setTimeout will be called immediately
                    if (next > 2147483647) {
                        exec = setTimeout(this.exec, 2147483647, recur, startDate, callback, arg);
                    }
                    else {
                        exec = setTimeout(this.handleExec, next, this, recur, callback, arg);
                    }

                    return true;
                }
            },

            /**
            * Immediately stops the execution of the current timer if one
            * exists.
            *
            * @api public
            */
            stopExec: function () {
                if (exec) {
                    clearTimeout(exec);
                    exec = false;
                }
            },

            /**
            * Handles the execution of the timer.
            *
            * @param {Later} later: The context to execute within
            * @param {Recur} recur: The set of constraints to use
            * @param {Func} callback: The function to execute
            * @param {arg[]} arg: Argument or array of arguments to pass to the
            *                     callback
            */
            handleExec: function (later, recur, callback, arg) {
                callback(arg);
                if (exec) {
                    later.exec(recur, (new Date()), callback, arg);
                }
            }

        };
    };

    /**
    * Allow library to be used within both the browser and node.js
    */
    var root = typeof exports !== "undefined" && exports !== null ? exports : window;
    root.later = Later;

}).call(this);



/**
* Later.js 0.0.1
* (c) 2012 Bill, BunKat LLC.
* Later is freely distributable under the MIT license.
* For all details and documentation:
*     http://bunkat.github.com/later
*/
(function () {

    "use strict";

    /**
    * Parses a cron expression and produces a schedule that is compatible
    * with Later.js.  See http://en.wikipedia.org/wiki/Cron for details of
    * the cron format.
    */
    var CronParser = function () {
    
        // Constant array to convert valid names to values
        var NAMES = {
            JAN: 1, FEB: 2, MAR: 3, APR: 4, MAY: 5, JUN: 6, JUL: 7, AUG: 8,
            SEP: 9, OCT: 10, NOV: 11, DEC: 12,
            SUN: 1, MON: 2, TUE: 3, WED: 4, THU: 5, FRI: 6, SAT: 7
        };

        // Contains the index, min, and max for each of the constraints
        var FIELDS = {
            s: [0, 0, 59],      // seconds
            m: [1, 0, 59],      // minutes
            h: [2, 0, 23],      // hours
            D: [3, 1, 31],      // day of month
            M: [4, 1, 12],  // month
            Y: [6, 1970, 2099], // year
            d: [5, 1, 7, 1]        // day of week
        };

        /**
        * Returns the value + offset if value is a number, otherwise it
        * attempts to look up the value in the NAMES table and returns
        * that result instead. 
        *
        * @param {Int,String} value: The value that should be parsed
        * @param {Int} offset: Any offset that must be added to the value
        */
        var getValue = function(value, offset) {
            return isNaN(value) ? NAMES[value] : +value + (offset || 0);
        };

        /**
        * Returns a deep clone of a schedule skipping any day of week
        * constraints.
        *
        * @param {Sched} sched: The schedule that will be cloned
        */
        var cloneSchedule = function(sched) {
            var clone = {}, field;

            for(field in sched) {
                if (field !== 'dc' && field !== 'd') {
                    clone[field] = sched[field].slice(0);
                }
            }

            return clone;
        };

        /**
        * Adds values to the specified constraint in the current schedule.
        *
        * @param {Sched} sched: The schedule to add the constraint to
        * @param {String} name: Name of constraint to add
        * @param {Int} min: Minimum value for this constraint
        * @param {Int} max: Maximum value for this constraint
        * @param {Int} inc: The increment to use between min and max
        */
        var add = function (sched, name, min, max, inc) {
            var i = min;

            if (!sched[name]) {
                sched[name] = [];
            }

            while (i <= max) {
                if (sched[name].indexOf(i) < 0) {
                    sched[name].push(i);
                } 
                i += inc || 1;              
            }       
        };

        /**
        * Adds a hash item (of the form x#y or xL) to the schedule.  
        *
        * @param {Schedule} schedules: The current schedule array to add to
        * @param {Schedule} curSched: The current schedule to add to
        * @param {Int} value: The value to add (x of x#y or xL)
        * @param {Int} hash: The hash value to add (y of x#y)
        */
        var addHash = function(schedules, curSched, value, hash) {
            // if there are any existing day of week constraints that
            // aren't equal to the one we're adding, create a new
            // composite schedule
            if ((curSched.d && !curSched.dc) || 
                    (curSched.dc && curSched.dc.indexOf(hash) < 0)) {
                schedules.push(cloneSchedule(curSched));
                curSched = schedules[schedules.length-1];
            }

            add(curSched, 'd', value, value);
            add(curSched, 'dc', hash, hash);          
        };


        var addWeekday = function(s, curSched, value) {
             var except1 = {}, except2 = {};
             if (value=== 1) {
                // cron doesn't pass month boundaries, so if 1st is a
                // weekend then we need to use 2nd or 3rd instead
                add(curSched, 'D', 1, 3);
                add(curSched, 'd', NAMES.MON, NAMES.FRI);
                add(except1, 'D', 2, 2);
                add(except1, 'd', NAMES.TUE, NAMES.FRI); 
                add(except2, 'D', 3, 3);
                add(except2, 'd', NAMES.TUE, NAMES.FRI); 
            } else {
                // normally you want the closest day, so if v is a
                // Saturday, use the previous Friday.  If it's a
                // sunday, use the following Monday.
                add(curSched, 'D', value-1, value+1);
                add(curSched, 'd', NAMES.MON, NAMES.FRI);
                add(except1, 'D', value-1, value-1);
                add(except1, 'd', NAMES.MON, NAMES.THU); 
                add(except2, 'D', value+1, value+1);
                add(except2, 'd', NAMES.TUE, NAMES.FRI);                 
            }
            s.exceptions.push(except1);
            s.exceptions.push(except2);           
        };

        /**
        * Adds a range item (of the form x-y/z) to the schedule.  
        *
        * @param {String} item: The cron expression item to add
        * @param {Schedule} curSched: The current schedule to add to
        * @param {String} name: The name to use for this constraint
        * @param {Int} min: The min value for the constraint
        * @param {Int} max: The max value for the constraint
        * @param {Int} offset: The offset to apply to the cron value
        */
        var addRange = function(item, curSched, name, min, max, offset) {
            // parse range/x
            var incSplit = item.split('/')
              , inc = +incSplit[1]
              , range = incSplit[0];

            // parse x-y or * or 0
            if (range !== '*' && range !== '0') {
                var rangeSplit = range.split('-');
                min = getValue(rangeSplit[0], offset);
                max = getValue(rangeSplit[1], offset);
            }
            add(curSched, name, min, max, inc);           
        };

        /**
        * Parses a particular item within a cron expression.  
        *
        * @param {String} item: The cron expression item to parse
        * @param {Schedule} s: The existing set of schedules
        * @param {String} name: The name to use for this constraint
        * @param {Int} min: The min value for the constraint
        * @param {Int} max: The max value for the constraint
        * @param {Int} offset: The offset to apply to the cron value
        */
        var parse = function(item, s, name, min, max, offset) {
            var value
              , split
              , schedules = s.schedules
              , curSched = schedules[schedules.length-1];

            // L just means min - 1 (this also makes it work for any field)
            if (item === 'L') {
                item = min - 1;
            }
            
            // parse x
            if ((value = getValue(item, offset)) != null) {
                add(curSched, name, value, value);
            }
            // parse xW
            else if ((value = getValue(item.replace('W', ''), offset)) != null) {
                addWeekday(s, curSched, value);
            }
            // parse xL
            else if ((value = getValue(item.replace('L', ''), offset)) != null) {
                addHash(schedules, curSched, value, min-1);
            }
            // parse x#y
            else if ((split = item.split('#')).length === 2) {
                value = getValue(split[0], offset);
                addHash(schedules, curSched, value, getValue(split[1]));
            }
            // parse x-y or x-y/z or */z or 0/z 
            else {
                addRange(item, curSched, name, min, max, offset);
            }
            
        };

        /**
        * Returns true if the item is either of the form x#y or xL.
        *
        * @param {String} item: The expression item to check
        */
        var isHash = function(item) {
            return item.indexOf('#') > -1 || item.indexOf('L') > 0;
        };


        var itemSorter = function(a,b) {
          return isHash(a) && !isHash(b) ? 1 : 0; 
        };

        /**
        * Parses each of the fields in a cron expression.  The expression must
        * include the seconds field, the year field is optional.
        *
        * @param {String} expr: The cron expression to parse
        */
        var parseExpr = function(expr) {
            var schedule = {schedules: [{}], exceptions: []}   
              , components = expr.split(' ')
              , field, f, component, items;

            for(field in FIELDS) {
                f = FIELDS[field];
                component = components[f[0]];
                if (component && component !== '*' && component !== '?') {
                    // need to sort so that any #'s come last, otherwise
                    // schedule clones to handle # won't contain all of the 
                    // other constraints
                    items = component.split(',').sort(itemSorter);
                    var i, length = items.length;
                    for (i = 0; i < length; i++) {    
                        parse(items[i], schedule, field, f[1], f[2], f[3]);
                    }
                }
            }

            return schedule;
        };

        return {

            /**
            * Parses a valid cron expression and produces a valid schedule that
            * can then be used with Later.
            *
            * CronParser().parse('* 5 * * * * *', true);
            *
            * @param {String} expr: The cron expression to parse
            * @param {Bool} hasSeconds: True if the expression uses a seconds field
            * @api public
            */
            parse: function (expr, hasSeconds) { 
                var e = expr.toUpperCase();
                return parseExpr(hasSeconds ? e : '0 ' + e); 
            }

        };
    };

    /**
    * Allow library to be used within both the browser and node.js
    */
    var root = typeof exports !== "undefined" && exports !== null ? exports : window;
    root.cronParser = CronParser;  

}).call(this);