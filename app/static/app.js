// Times are stored in UTC on the server. Here we show and send them in the visitor's local time.
(function () {
  // hi/gu: the "-u-nu-..." part asks for Hindi / Gujarati digits (browsers use 0-9 by default)
  var locale = { hi: 'hi-IN-u-nu-deva', gu: 'gu-IN-u-nu-gujr' }[document.documentElement.lang]; // others: browser default

  // 1) <time data-utc="..."> elements: show local time
  document.querySelectorAll('time[data-utc]').forEach(function (el) {
    var d = new Date(el.getAttribute('data-utc'));
    if (!isNaN(d)) el.textContent = d.toLocaleString(locale, { dateStyle: 'medium', timeStyle: 'short' });
  });

  // 2) remember the visitor's time zone, so day-by-day stats use their own days (not UTC days)
  try {
    var zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (zone && document.cookie.indexOf('tz=' + zone) === -1) {
      document.cookie = 'tz=' + zone + '; path=/; max-age=31536000; SameSite=Lax' +
        (location.protocol === 'https:' ? '; Secure' : '');
    }
  } catch (e) { /* no time zone info: the server falls back to UTC */ }

  // 3) edit page: only show the "new password" box when "set/change" is selected
  document.querySelectorAll('.new-password').forEach(function (box) {
    var form = box.closest('form');
    var radios = form.querySelectorAll('input[name="password_action"]');
    function sync() {
      var chosen = form.querySelector('input[name="password_action"]:checked');
      box.hidden = !chosen || chosen.value !== 'set';
    }
    radios.forEach(function (r) { r.addEventListener('change', sync); });
    sync();
  });
})();
