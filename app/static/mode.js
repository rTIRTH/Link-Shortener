// The small light / system default / dark button in the top bar. One tap goes to the next mode
// (light, then system default, then dark, then light again): the page changes at once and the
// choice is saved in the background. Without this script the button is an ordinary form.
(function () {
  var form = document.querySelector('[data-mode-button]');
  if (!form) return;
  var button = form.querySelector('button');
  var status = form.querySelector('[data-mode-status]');
  var names = JSON.parse(button.getAttribute('data-names') || '{}');
  var template = button.getAttribute('data-aria') || '';
  var ORDER = ['light', 'system', 'dark'];

  function paint(mode) {
    var next = ORDER[(ORDER.indexOf(mode) + 1) % ORDER.length];
    var text = template.replace('{mode}', names[mode]).replace('{next}', names[next]);
    button.setAttribute('aria-label', text);
    button.title = text;
    button.value = next; // what the next tap will choose
    if (status) status.textContent = names[mode];
    document.querySelectorAll('input[type="radio"][name="theme"]').forEach(function (r) {
      r.checked = r.value === mode; // keep the radio buttons on the Account page in step
    });
  }

  function choose(mode) {
    document.documentElement.dataset.theme = mode; // the icon follows from this, in the stylesheet
    paint(mode);
    fetch('/mode', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json' },
      body: 'theme=' + encodeURIComponent(mode)
    }).catch(function () { /* offline: the page still changed, it just was not saved */ });
  }

  button.addEventListener('click', function (e) { e.preventDefault(); choose(button.value); });
  if (status) status.textContent = '';
  paint(document.documentElement.dataset.theme || 'system');
  if (status) status.textContent = ''; // say nothing until the person taps
})();
