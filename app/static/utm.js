// Campaign tracking boxes: show the address visitors will really land on, as the person types.
(function () {
  var KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];

  function finalAddress(raw, boxes) {
    var text = (raw || '').trim();
    if (!text) return '';
    if (text.indexOf('://') === -1) text = 'https://' + text;
    var url;
    try { url = new URL(text); } catch (e) { return ''; }
    var typed = {};
    KEYS.forEach(function (k) {
      if (url.searchParams.has(k)) { typed[k] = url.searchParams.get(k); url.searchParams.delete(k); }
    });
    var extra = [];
    KEYS.forEach(function (k) {
      var value = (boxes[k] || typed[k] || '').trim().replace(/\s+/g, ' ');
      if (value) extra.push(k + '=' + encodeURIComponent(value)); // the boxes win over the address
    });
    if (!extra.length) return '';
    url.search = [url.searchParams.toString()].concat(extra).filter(Boolean).join('&');
    return url.href;
  }

  function update(scope) {
    var urlBox = scope.querySelector('[data-utm-url]');
    var out = scope.querySelector('[data-utm-final]');
    if (!urlBox || !out) return;
    var boxes = {};
    scope.querySelectorAll('[data-utm-input]').forEach(function (box) {
      boxes[box.getAttribute('data-utm-input')] = box.value;
    });
    var address = finalAddress(urlBox.value, boxes);
    out.textContent = address;
    var wrap = out.closest('[data-utm-final-wrap]');
    if (wrap) wrap.hidden = !address;
  }

  document.querySelectorAll('[data-utm-scope]').forEach(function (scope) {
    scope.addEventListener('input', function () { update(scope); });
    update(scope);
  });
})();
