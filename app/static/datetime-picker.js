/* Date and time picker.
 *
 *  - Type a date like "Sunday, 11/10/2026" (the weekday is corrected for you),
 *    optionally followed by a time like "09:30:15 PM".
 *  - Or open the calendar: pick a day, then use the hour / minute / second wheels
 *    (they loop: scroll past 59 and you are back at 00) and AM / PM.
 *  - The page shows local time. A hidden field "<name>_utc" carries the exact moment
 *    in UTC to the server.
 */
(function () {
  'use strict';

  var MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
    'September', 'October', 'November', 'December'];
  var WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var SHORT = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
  var ROWS = 7;      // rows visible in a time wheel
  var CENTER = 3;    // index of the selected (middle) row
  var current = null; // the picker whose popup is open

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function mod(a, n) { return ((a % n) + n) % n; }
  function daysIn(y, m) { return new Date(y, m, 0).getDate(); } // m is 1-12
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function button(cls, text, label) {
    var b = el('button', cls, text);
    b.type = 'button';
    if (label) b.setAttribute('aria-label', label);
    return b;
  }
  function range(from, to, width) {
    var out = [];
    for (var i = from; i <= to; i++) out.push(width ? pad(i) : String(i));
    return out;
  }

  // "Sunday, 11/10/2026, 09:30:15 PM"
  function format(d, t) {
    var dow = new Date(d.y, d.m - 1, d.d).getDay();
    return WEEKDAYS[dow] + ', ' + pad(d.d) + '/' + pad(d.m) + '/' + d.y + ', ' +
      pad(t.h % 12 || 12) + ':' + pad(t.mi) + ':' + pad(t.s) + ' ' + (t.h >= 12 ? 'PM' : 'AM');
  }

  // Reads typed text. Returns { date: {y,m,d}, time: {h,mi,s} | null } or null if invalid.
  function parseText(text) {
    var m = /(\d{1,2})\s*[\/.\-]\s*(\d{1,2})\s*[\/.\-]\s*(\d{4})/.exec(text);
    if (!m) return null;
    var d = +m[1], mo = +m[2], y = +m[3];
    if (y < 2000 || y > 2100 || mo < 1 || mo > 12 || d < 1 || d > daysIn(y, mo)) return null;
    var rest = text.slice(m.index + m[0].length);
    var t = /(\d{1,2})\s*:\s*(\d{2})(?:\s*:\s*(\d{2}))?(?:\s*([AaPp])\.?\s*[Mm]\.?)?/.exec(rest);
    var time = null;
    if (t) {
      var h = +t[1], mi = +t[2], s = t[3] ? +t[3] : 0;
      if (mi > 59 || s > 59) return null;
      if (t[4]) {
        if (h < 1 || h > 12) return null;
        h = (h % 12) + (t[4].toLowerCase() === 'p' ? 12 : 0);
      } else if (h > 23) {
        return null;
      }
      time = { h: h, mi: mi, s: s };
    } else if (/\d/.test(rest)) {
      return null; // leftover digits we could not understand
    }
    return { date: { y: y, m: mo, d: d }, time: time };
  }

  // A looping wheel: shows 7 values around the selected one and wraps at both ends.
  function makeWheel(label, values, onChange) {
    var n = values.length, idx = 0, acc = 0;
    var root = el('div', 'dtp-wheel');
    root.tabIndex = 0;
    root.setAttribute('role', 'spinbutton');
    root.setAttribute('aria-label', label);
    var items = [];
    for (var r = 0; r < ROWS; r++) {
      var it = el('div', 'dtp-item');
      items.push(it);
      root.appendChild(it);
    }
    function paint() {
      items.forEach(function (item, row) {
        var offset = row - CENTER;
        item.textContent = values[mod(idx + offset, n)];
        item.className = 'dtp-item o' + Math.abs(offset);
        item.setAttribute('data-offset', offset);
      });
      root.setAttribute('aria-valuenow', idx);
      root.setAttribute('aria-valuetext', values[idx]);
    }
    function step(k) {
      if (!k) return;
      idx = mod(idx + k, n);
      paint();
      onChange(idx);
    }
    function set(i) { idx = mod(i, n); paint(); }

    root.addEventListener('wheel', function (e) {
      e.preventDefault(); // scroll the wheel, not the page
      var dy = e.deltaY;
      if (e.deltaMode === 1) dy *= 16; else if (e.deltaMode === 2) dy *= 100;
      if (Math.abs(dy) >= 50) {            // a mouse notch
        acc = 0;
        step((dy > 0 ? 1 : -1) * Math.max(1, Math.round(Math.abs(dy) / 100)));
      } else {                              // trackpad: collect small movements
        acc += dy;
        if (Math.abs(acc) >= 30) { step(acc > 0 ? 1 : -1); acc = 0; }
      }
    }, { passive: false });

    root.addEventListener('keydown', function (e) {
      var k = { ArrowDown: 1, ArrowUp: -1, PageDown: 5, PageUp: -5 }[e.key];
      if (k) { e.preventDefault(); step(k); }
    });

    // dragging with a finger or mouse
    var lastY = null, carry = 0, travel = 0;
    root.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' && e.button !== 0) return;
      lastY = e.clientY; carry = 0; travel = 0;
      try { root.setPointerCapture(e.pointerId); } catch (err) { /* not supported */ }
    });
    root.addEventListener('pointermove', function (e) {
      if (lastY === null) return;
      var dy = lastY - e.clientY;
      lastY = e.clientY;
      carry += dy; travel += Math.abs(dy);
      var k = Math.trunc(carry / 28);
      if (k) { carry -= k * 28; step(k); }
    });
    function endDrag() { lastY = null; }
    root.addEventListener('pointerup', endDrag);
    root.addEventListener('pointercancel', endDrag);
    root.addEventListener('click', function (e) {
      if (travel > 4) { travel = 0; return; } // that was a drag, not a click
      var item = e.target.closest('.dtp-item');
      if (item) step(parseInt(item.getAttribute('data-offset'), 10));
    });

    paint();
    return { el: root, set: set };
  }

  function Picker(root) {
    var input = root.querySelector('.dtp-input');
    var hidden = root.querySelector('input[type="hidden"]');
    var toggle = root.querySelector('.dtp-toggle');
    var errBox = root.parentNode.querySelector('.dtp-error');
    var kind = root.getAttribute('data-kind') === 'end' ? 'end' : 'start';
    var DEFAULT = kind === 'end' ? { h: 23, mi: 59, s: 59 } : { h: 0, mi: 0, s: 0 };

    var sel = null;                                   // chosen day {y,m,d} or null
    var time = { h: DEFAULT.h, mi: DEFAULT.mi, s: DEFAULT.s };
    var today = new Date();
    var view = { y: today.getFullYear(), m: today.getMonth() + 1 };
    var focusDay = 1;
    var popup = null, ui = {}, isOpen = false;

    function todayObj() {
      var t = new Date();
      return { y: t.getFullYear(), m: t.getMonth() + 1, d: t.getDate() };
    }
    function example() {
      var t = todayObj();
      return format(t, { h: 0, mi: 0, s: 0 }).split(', ').slice(0, 2).join(', ');
    }
    function showError(msg) {
      if (!errBox) return;
      errBox.hidden = !msg;
      errBox.textContent = msg || '';
      input.setAttribute('aria-invalid', msg ? 'true' : 'false');
    }
    function toISO() {
      return new Date(sel.y, sel.m - 1, sel.d, time.h, time.mi, time.s).toISOString();
    }
    function updateHidden() { hidden.value = sel ? toISO() : ''; }
    function commit() {
      input.value = sel ? format(sel, time) : '';
      updateHidden();
      showError('');
    }
    function setFromDate(dt) {
      sel = { y: dt.getFullYear(), m: dt.getMonth() + 1, d: dt.getDate() };
      time = { h: dt.getHours(), mi: dt.getMinutes(), s: dt.getSeconds() };
      view = { y: sel.y, m: sel.m };
    }
    function ensureDate() {
      if (!sel) { sel = todayObj(); view = { y: sel.y, m: sel.m }; }
    }

    // ----- text box -----
    function applyText() {
      var text = input.value.trim();
      if (!text) { sel = null; commit(); syncUI(); return true; }
      var parsed = parseText(text);
      if (!parsed) { showError('Use a date like ' + example() + ', optionally with a time like 09:30 PM.'); return false; }
      sel = parsed.date;
      if (parsed.time) time = parsed.time;
      view = { y: sel.y, m: sel.m };
      commit();
      syncUI();
      return true;
    }

    // ----- calendar -----
    function ensureYear(y) {
      var thisYear = new Date().getFullYear();
      var from = Math.max(2000, Math.min(y, thisYear - 1)), to = Math.min(2100, Math.max(y, thisYear + 10));
      var have = ui.year.options;
      if (have.length && +have[0].value <= from && +have[have.length - 1].value >= to) return;
      ui.year.textContent = '';
      for (var i = from; i <= to; i++) {
        var o = el('option', null, String(i));
        o.value = i;
        ui.year.appendChild(o);
      }
    }

    function renderCalendar() {
      if (!popup) return;
      ensureYear(view.y);
      ui.month.value = view.m;
      ui.year.value = view.y;
      ui.grid.textContent = '';
      var t = todayObj();
      var first = new Date(view.y, view.m - 1, 1).getDay();
      var count = daysIn(view.y, view.m);
      for (var b = 0; b < first; b++) ui.grid.appendChild(el('span', 'dtp-blank')); // empty: no days of other months
      for (var d = 1; d <= count; d++) {
        var day = button('dtp-day', String(d));
        var dow = new Date(view.y, view.m - 1, d).getDay();
        day.setAttribute('data-day', d);
        day.setAttribute('aria-label', WEEKDAYS[dow] + ' ' + d + ' ' + MONTHS[view.m - 1] + ' ' + view.y);
        var isSel = sel && sel.y === view.y && sel.m === view.m && sel.d === d;
        var isToday = t.y === view.y && t.m === view.m && t.d === d;
        if (isSel) day.classList.add('sel');
        if (isToday) { day.classList.add('today'); day.setAttribute('aria-current', 'date'); }
        day.setAttribute('aria-pressed', isSel ? 'true' : 'false');
        day.tabIndex = d === focusDay ? 0 : -1;
        ui.grid.appendChild(day);
      }
    }

    function pickFocusDay() {
      var t = todayObj();
      if (sel && sel.y === view.y && sel.m === view.m) focusDay = sel.d;
      else if (t.y === view.y && t.m === view.m) focusDay = t.d;
      else focusDay = 1;
    }
    function goMonth(delta) {
      var d = new Date(view.y, view.m - 1 + delta, 1);
      view = { y: Math.min(2100, Math.max(2000, d.getFullYear())), m: d.getMonth() + 1 };
      focusDay = Math.min(focusDay, daysIn(view.y, view.m));
      renderCalendar();
    }
    function focusButton() {
      var b = ui.grid.querySelector('[data-day="' + focusDay + '"]');
      if (b) b.focus();
    }

    // ----- time -----
    function syncWheels() {
      if (!popup) return;
      ui.hour.set((time.h % 12 || 12) - 1);
      ui.minute.set(time.mi);
      ui.second.set(time.s);
      ui.am.setAttribute('aria-pressed', time.h < 12 ? 'true' : 'false');
      ui.pm.setAttribute('aria-pressed', time.h >= 12 ? 'true' : 'false');
    }
    function syncUI() {
      if (!popup) return;
      pickFocusDay();
      renderCalendar();
      syncWheels();
    }
    function timeChanged() {
      ensureDate();
      commit();
      pickFocusDay();
      renderCalendar();
    }
    function setPeriod(pm) {
      time.h = (time.h % 12) + (pm ? 12 : 0);
      syncWheels();
      timeChanged();
    }

    // ----- popup -----
    function build() {
      popup = el('div', 'dtp-popup');
      popup.hidden = true;
      popup.setAttribute('role', 'dialog');
      popup.setAttribute('aria-label', 'Choose ' + kind + ' date and time');
      // clicking blank space inside must not steal focus away and close the popup
      popup.addEventListener('mousedown', function (e) {
        if (!e.target.closest('button, select, input, [tabindex]')) e.preventDefault();
      });

      var cal = el('div', 'dtp-cal');
      var head = el('div', 'dtp-head');
      ui.prev = button('dtp-nav', '\u2039', 'Previous month');
      ui.next = button('dtp-nav', '\u203A', 'Next month');
      ui.month = el('select');
      ui.month.setAttribute('aria-label', 'Month');
      MONTHS.forEach(function (name, i) { var o = el('option', null, name); o.value = i + 1; ui.month.appendChild(o); });
      ui.year = el('select');
      ui.year.setAttribute('aria-label', 'Year');
      head.appendChild(ui.prev); head.appendChild(ui.month); head.appendChild(ui.year); head.appendChild(ui.next);
      var weekdays = el('div', 'dtp-weekdays');
      SHORT.forEach(function (s) { weekdays.appendChild(el('span', null, s)); });
      ui.grid = el('div', 'dtp-grid');
      ui.grid.setAttribute('role', 'group');
      ui.grid.setAttribute('aria-label', 'Days');
      cal.appendChild(head); cal.appendChild(weekdays); cal.appendChild(ui.grid);

      var box = el('div', 'dtp-time');
      box.appendChild(el('div', 'dtp-time-title', 'Time'));
      var cols = el('div', 'dtp-cols');
      var wh = makeWheel('Hour', range(1, 12, true), function (i) {
        time.h = ((i + 1) % 12) + (time.h >= 12 ? 12 : 0);
        timeChanged();
      });
      var wm = makeWheel('Minute', range(0, 59, true), function (i) { time.mi = i; timeChanged(); });
      var ws = makeWheel('Second', range(0, 59, true), function (i) { time.s = i; timeChanged(); });
      ui.hour = wh; ui.minute = wm; ui.second = ws;
      cols.appendChild(wh.el); cols.appendChild(el('span', 'dtp-colon', ':'));
      cols.appendChild(wm.el); cols.appendChild(el('span', 'dtp-colon', ':'));
      cols.appendChild(ws.el);
      var period = el('div', 'dtp-ampm');
      ui.am = button('dtp-period', 'AM', 'AM');
      ui.pm = button('dtp-period', 'PM', 'PM');
      ui.am.addEventListener('click', function () { setPeriod(false); });
      ui.pm.addEventListener('click', function () { setPeriod(true); });
      period.appendChild(ui.am); period.appendChild(ui.pm);
      cols.appendChild(period);
      box.appendChild(cols);

      var foot = el('div', 'dtp-foot');
      var clear = button('btn small ghost', 'Clear');
      var todayBtn = button('btn small ghost', 'Today');
      var done = button('btn small', 'Done');
      foot.appendChild(clear); foot.appendChild(todayBtn); foot.appendChild(done);

      popup.appendChild(cal); popup.appendChild(box); popup.appendChild(foot);
      root.appendChild(popup);

      ui.prev.addEventListener('click', function () { goMonth(-1); });
      ui.next.addEventListener('click', function () { goMonth(1); });
      ui.month.addEventListener('change', function () { view.m = +ui.month.value; goMonth(0); });
      ui.year.addEventListener('change', function () { view.y = +ui.year.value; goMonth(0); });
      ui.grid.addEventListener('click', function (e) {
        var b = e.target.closest('.dtp-day');
        if (!b) return;
        sel = { y: view.y, m: view.m, d: +b.getAttribute('data-day') };
        commit();
        pickFocusDay();
        renderCalendar();
        var again = ui.grid.querySelector('[data-day="' + focusDay + '"]');
        if (again && document.activeElement === document.body) again.focus();
      });
      ui.grid.addEventListener('keydown', function (e) {
        var delta = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
        if (delta !== undefined) {
          e.preventDefault();
          var next = new Date(view.y, view.m - 1, focusDay + delta);
          view = { y: next.getFullYear(), m: next.getMonth() + 1 };
          focusDay = next.getDate();
          renderCalendar();
          focusButton();
        } else if (e.key === 'PageUp' || e.key === 'PageDown') {
          e.preventDefault();
          goMonth(e.key === 'PageUp' ? -1 : 1);
          focusButton();
        }
      });
      clear.addEventListener('click', function () {
        sel = null;
        time = { h: DEFAULT.h, mi: DEFAULT.mi, s: DEFAULT.s };
        commit();
        syncUI();
      });
      todayBtn.addEventListener('click', function () {
        sel = todayObj();
        view = { y: sel.y, m: sel.m };
        commit();
        syncUI();
      });
      done.addEventListener('click', function () { api.close(); toggle.focus(); });
    }

    function place() {
      popup.classList.remove('align-right');
      var r = popup.getBoundingClientRect();
      if (r.right > window.innerWidth - 8) popup.classList.add('align-right');
    }

    var api = {
      root: root,
      open: function (viaButton) {
        if (isOpen) return;
        if (current && current !== api) current.close();
        if (!popup) build();
        popup.hidden = false;
        isOpen = true;
        current = api;
        toggle.setAttribute('aria-expanded', 'true');
        syncUI();
        place();
        if (viaButton) focusButton();
      },
      close: function () {
        if (!isOpen) return;
        popup.hidden = true;
        isOpen = false;
        if (current === api) current = null;
        toggle.setAttribute('aria-expanded', 'false');
      },
      isOpen: function () { return isOpen; },
      input: input,
      applyText: applyText
    };

    // ----- start up -----
    var iso = input.getAttribute('data-utc');
    var start = iso ? new Date(iso) : null;
    if (start && !isNaN(start)) {
      setFromDate(start);
      commit();
    } else if (input.value.trim()) {
      applyText();
    }
    input.placeholder = 'e.g. ' + example();

    toggle.addEventListener('click', function () { if (isOpen) api.close(); else api.open(true); });
    input.addEventListener('focus', function () { if (!api.skipOpen) api.open(false); });
    input.addEventListener('click', function () { api.open(false); });
    input.addEventListener('input', function () {
      var parsed = parseText(input.value);   // follow along while typing
      if (parsed) {
        sel = parsed.date;
        if (parsed.time) time = parsed.time;
        view = { y: sel.y, m: sel.m };
        updateHidden();
        showError('');
        syncUI();
      }
    });
    input.addEventListener('blur', function () { applyText(); });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && isOpen) { e.preventDefault(); if (applyText()) api.close(); }
    });
    if (input.form) {
      input.form.addEventListener('submit', function (e) {
        if (!applyText()) { e.preventDefault(); input.focus(); }
      });
    }
    return api;
  }

  document.addEventListener('pointerdown', function (e) {
    if (current && !current.root.contains(e.target)) current.close();
  });
  document.addEventListener('focusin', function (e) {
    if (current && !current.root.contains(e.target)) current.close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && current) {
      var picker = current;
      picker.close();
      picker.skipOpen = true;               // refocusing the box must not reopen the calendar
      picker.input.focus({ preventScroll: true });
      picker.skipOpen = false;
    }
  });

  var pickers = [];
  document.querySelectorAll('[data-dtp]').forEach(function (root) { pickers.push(Picker(root)); });
  window.__pickers = pickers; // handy for debugging in the browser console
})();
