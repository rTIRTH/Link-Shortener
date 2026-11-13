/* Copy buttons: any button with data-copy="..." copies that text and says so.
   Used next to "Redirects to ..." on the analytics page. */
(function () {
  'use strict';

  var DATA = {};
  try { DATA = JSON.parse(document.getElementById('i18n-data').textContent) || {}; } catch (e) { DATA = {}; }
  var UI = DATA.ui || {};

  function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(value);
    return new Promise(function (resolve, reject) { // older browsers: select a hidden box and copy
      var box = document.createElement('textarea');
      box.value = value;
      box.setAttribute('readonly', '');
      box.style.cssText = 'position:fixed;top:-1000px;opacity:0';
      document.body.appendChild(box);
      box.select();
      try { document.execCommand('copy') ? resolve() : reject(new Error('copy failed')); } catch (e) { reject(e); }
      document.body.removeChild(box);
    });
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest ? event.target.closest('[data-copy]') : null;
    if (!button) return;
    var tip = button.parentNode.querySelector('.copy-tip');
    function show(message, failed) {
      if (tip) { tip.textContent = message; tip.classList.toggle('bad', !!failed); }
      button.classList.toggle('done', !failed);
      clearTimeout(button._timer);
      button._timer = setTimeout(function () {
        button.classList.remove('done');
        if (tip) { tip.textContent = ''; tip.classList.remove('bad'); }
      }, 2200);
    }
    copyText(button.getAttribute('data-copy')).then(
      function () { show(UI.share_copied || 'Copied!', false); },
      function () { show(UI.share_copy_failed || 'Could not copy automatically. Select the link and copy it.', true); }
    );
  });
})();
