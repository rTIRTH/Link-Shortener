// Times are stored in UTC on the server. Here we show and send them in the visitor's local time.
(function () {
  function pad(n) { return String(n).padStart(2, '0'); }
  function toLocalInput(d) {
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
      'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  // 1) <time data-utc="..."> elements: show local time
  document.querySelectorAll('time[data-utc]').forEach(function (el) {
    var d = new Date(el.getAttribute('data-utc'));
    if (!isNaN(d)) el.textContent = d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  });

  // 2) date-time inputs: pre-filled with UTC by the server, so convert to local for editing
  document.querySelectorAll('input[type="datetime-local"][data-utc]').forEach(function (input) {
    var raw = input.getAttribute('data-utc');
    var d = raw ? new Date(raw) : null;
    if (d && !isNaN(d)) input.value = toLocalInput(d);
  });

  // 3) on submit, send the exact UTC moment in a hidden field called "<name>_utc"
  document.querySelectorAll('form').forEach(function (form) {
    var inputs = form.querySelectorAll('input[type="datetime-local"]');
    if (!inputs.length) return;
    form.addEventListener('submit', function () {
      inputs.forEach(function (input) {
        var hidden = form.querySelector('input[name="' + input.name + '_utc"]');
        if (!hidden) return;
        var d = input.value ? new Date(input.value) : null;
        hidden.value = d && !isNaN(d) ? d.toISOString() : '';
      });
    });
  });

  // 4) edit page: only show the "new password" box when "set/change" is selected
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
