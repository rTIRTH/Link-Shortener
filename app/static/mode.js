// The light / system default / dark switch in the top bar: changes the page at once and saves the
// choice in the background. Without this script the buttons are an ordinary form that reloads.
(function () {
  var form = document.querySelector('[data-mode-switch]');
  if (!form) return;
  var buttons = [].slice.call(form.querySelectorAll('button'));

  function paint(mode) {
    buttons.forEach(function (b) {
      var on = b.value === mode;
      b.classList.toggle('on', on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1; // one tab stop for the group; the arrow keys move inside it
    });
    document.querySelectorAll('input[type="radio"][name="theme"]').forEach(function (r) {
      r.checked = r.value === mode; // keep the radio buttons on the Account page in step
    });
  }

  function choose(mode) {
    document.documentElement.dataset.theme = mode;
    paint(mode);
    fetch('/mode', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json' },
      body: 'theme=' + encodeURIComponent(mode)
    }).catch(function () { /* offline: the page still changed, it just was not saved */ });
  }

  buttons.forEach(function (b) {
    b.addEventListener('click', function (e) { e.preventDefault(); choose(b.value); });
  });

  form.addEventListener('keydown', function (e) {
    var at = buttons.indexOf(document.activeElement);
    if (at === -1) return;
    var to = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') to = (at + 1) % buttons.length;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') to = (at + buttons.length - 1) % buttons.length;
    else if (e.key === 'Home') to = 0;
    else if (e.key === 'End') to = buttons.length - 1;
    if (to === null) return;
    e.preventDefault();
    buttons[to].focus();
    choose(buttons[to].value);
  });

  paint(document.documentElement.dataset.theme || 'system');
})();
