// Times are stored in UTC on the server. Here we show and send them in the visitor's local time.
(function () {
  // 1) <time data-utc="..."> elements: show local time
  document.querySelectorAll('time[data-utc]').forEach(function (el) {
    var d = new Date(el.getAttribute('data-utc'));
    if (!isNaN(d)) el.textContent = d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  });

  // 2) edit page: only show the "new password" box when "set/change" is selected
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
