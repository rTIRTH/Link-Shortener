/* Bulk page: pick links, tick "Change this" next to the settings to change, confirm, send.
 *
 *  - Each setting's choices stay switched off (and are not sent) until its "Change this" box is ticked.
 *  - "Select all" and the count of ticked links.
 *  - The button wakes up when at least one link and one setting are ticked (and not too many links).
 *  - Pressing it asks "This will change N links. Continue?".
 * Without JavaScript the page still works: the server only looks at the settings that are ticked.
 */
(function () {
  'use strict';
  var form = document.getElementById('bulk-form');
  if (!form) return;

  var DATA = {};
  try { DATA = JSON.parse(document.getElementById('i18n-data').textContent) || {}; } catch (e) { DATA = {}; }
  var DIGITS = DATA.digits || '';   // Hindi / Gujarati show their own digits; '' = keep 0-9
  function nd(value) {
    var text = String(value);
    return DIGITS ? text.replace(/[0-9]/g, function (c) { return DIGITS.charAt(+c); }) : text;
  }
  function say(template, n) { return String(template || '').replace('{n}', nd(n)); }

  var locked = form.getAttribute('data-locked') === '1';
  var max = parseInt(form.getAttribute('data-max'), 10) || 200;
  var picks = Array.prototype.slice.call(form.querySelectorAll('.bulk-pick'));
  var all = document.getElementById('bulk-all');
  var count = document.getElementById('bulk-count');
  var go = document.getElementById('bulk-go');
  var toggles = Array.prototype.slice.call(form.querySelectorAll('.bs-toggle'));

  function controls(toggle) {
    var body = toggle.closest('.bs').querySelector('.bs-body');
    return Array.prototype.slice.call(body.querySelectorAll('input, select, textarea, button'));
  }

  function sync() {
    var n = picks.filter(function (c) { return c.checked; }).length;
    var any = toggles.some(function (t) { return t.checked; });
    if (count) {
      count.textContent = n > max ? say(form.getAttribute('data-toomany'), max)
        : say(form.getAttribute(n === 1 ? 'data-one' : 'data-many'), n);
      count.classList.toggle('over', n > max);
    }
    if (all) {
      all.checked = n > 0 && n === picks.length;
      all.indeterminate = n > 0 && n < picks.length;
    }
    if (go) go.disabled = locked || n === 0 || n > max || !any;
    toggles.forEach(function (t) {
      t.closest('.bs').classList.toggle('on', t.checked);
      controls(t).forEach(function (c) {
        if (c.getAttribute('data-locked') !== '1') c.disabled = !t.checked;
      });
    });
  }

  if (all) {
    all.addEventListener('change', function () {
      picks.forEach(function (c) { c.checked = all.checked; });
      sync();
    });
  }
  picks.forEach(function (c) { c.addEventListener('change', sync); });
  toggles.forEach(function (t) { t.addEventListener('change', sync); });

  form.addEventListener('submit', function (e) {
    var n = picks.filter(function (c) { return c.checked; }).length;
    if (!window.confirm(say(form.getAttribute('data-confirm'), n))) e.preventDefault();
  });

  form.classList.add('ready');
  sync();
})();
