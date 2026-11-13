/* Share pop-up on the dashboard: pick one link, press Share.
   Copy link, Download QR, and a grid of apps. "More" opens the device's own share sheet
   where the browser has one, and otherwise shows a few more apps. */
(function () {
  'use strict';

  var dialog = document.getElementById('share-dialog');
  var openBtn = document.getElementById('share-selected');
  if (!dialog || !openBtn || typeof dialog.showModal !== 'function') return;

  var DATA = {};
  try { DATA = JSON.parse(document.getElementById('i18n-data').textContent) || {}; } catch (e) { DATA = {}; }
  var UI = DATA.ui || {};

  var urlBox = document.getElementById('share-url');
  var copyBtn = document.getElementById('share-copy');
  var qrLink = document.getElementById('share-qr');
  var note = document.getElementById('share-note');
  var status = document.getElementById('share-status');
  var more = document.getElementById('share-more');
  var extra = document.getElementById('share-extra');
  var apps = Array.prototype.slice.call(dialog.querySelectorAll('[data-app]'));
  var text = dialog.getAttribute('data-text') || '';
  var copyText_ = copyBtn.querySelector('span') || copyBtn; // the words, so the icon stays
  var copyLabel = copyText_.textContent;
  var resetTimer = null;
  var current = null; // { url, id, slug, status } of the link being shared

  function enc(value) { return encodeURIComponent(value); }

  // Where each app wants to be sent: the link, and a short line of text.
  var ADDRESS = {
    whatsapp: function (u, t) { return 'https://wa.me/?text=' + enc(t + ' ' + u); },
    telegram: function (u, t) { return 'https://t.me/share/url?url=' + enc(u) + '&text=' + enc(t); },
    gmail: function (u, t) {
      return 'https://mail.google.com/mail/?view=cm&fs=1&su=' + enc(t) + '&body=' + enc(t + '\n' + u);
    },
    email: function (u, t) { return 'mailto:?subject=' + enc(t) + '&body=' + enc(t + '\n' + u); },
    facebook: function (u) { return 'https://www.facebook.com/sharer/sharer.php?u=' + enc(u); },
    x: function (u, t) { return 'https://x.com/intent/post?url=' + enc(u) + '&text=' + enc(t); },
    linkedin: function (u) { return 'https://www.linkedin.com/sharing/share-offsite/?url=' + enc(u); },
    reddit: function (u, t) { return 'https://www.reddit.com/submit?url=' + enc(u) + '&title=' + enc(t); },
    pinterest: function (u, t) {
      return 'https://www.pinterest.com/pin/create/button/?url=' + enc(u) + '&description=' + enc(t);
    },
    tumblr: function (u, t) {
      return 'https://www.tumblr.com/widgets/share/tool?canonicalUrl=' + enc(u) + '&caption=' + enc(t);
    },
    line: function (u) { return 'https://social-plugins.line.me/lineit/share?url=' + enc(u); }
  };

  function selectedLink() {
    var ticked = Array.prototype.slice.call(document.querySelectorAll('.pick')).filter(function (c) { return c.checked; });
    if (ticked.length !== 1) return null; // Share is for exactly one link
    var box = ticked[0];
    return {
      url: box.getAttribute('data-url'), id: box.getAttribute('data-id'),
      slug: box.getAttribute('data-slug'), status: box.getAttribute('data-status')
    };
  }

  // A screen reader hears every message; it is only drawn on screen for a problem (the button already says Copied!)
  function say(message, visible) {
    status.textContent = message || '';
    status.classList.toggle('show', !!(message && visible));
  }

  function resetCopyButton() {
    clearTimeout(resetTimer);
    copyText_.textContent = copyLabel;
    say('');
  }

  // Copy: the modern clipboard where allowed, otherwise select the box and use the old way.
  function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(value);
    return new Promise(function (resolve, reject) {
      urlBox.focus();
      urlBox.select();
      try { document.execCommand('copy') ? resolve() : reject(new Error('copy failed')); } catch (e) { reject(e); }
    });
  }

  openBtn.addEventListener('click', function () {
    current = selectedLink();
    if (!current) return;
    resetCopyButton();
    urlBox.value = current.url;
    qrLink.href = '/dashboard/links/' + current.id + '/qr.png?download=1';
    qrLink.setAttribute('download', current.slug + '-qr.png');
    note.hidden = current.status === 'active';
    apps.forEach(function (a) {
      var make = ADDRESS[a.getAttribute('data-app')];
      if (make) a.href = make(current.url, text);
      if (a.getAttribute('data-app') === 'email') a.removeAttribute('target'); // mailto: opens the mail app
    });
    extra.hidden = true;
    more.setAttribute('aria-expanded', 'false');
    dialog.showModal();
  });

  copyBtn.addEventListener('click', function () {
    if (!current) return;
    copyText(current.url).then(function () {
      copyText_.textContent = UI.share_copied || 'Copied!';
      say(UI.share_copied || 'Copied!');
      clearTimeout(resetTimer);
      resetTimer = setTimeout(resetCopyButton, 2200);
    }, function () {
      urlBox.focus();
      urlBox.select();
      say(UI.share_copy_failed || 'Could not copy automatically. Select the link and copy it.', true);
    });
  });

  more.addEventListener('click', function () {
    if (!current) return;
    if (navigator.share) { // the phone's or computer's own list of apps
      navigator.share({ title: text, text: text, url: current.url }).catch(function () { /* cancelled */ });
      return;
    }
    extra.hidden = !extra.hidden; // no share sheet in this browser: show a few more apps here
    more.setAttribute('aria-expanded', extra.hidden ? 'false' : 'true');
  });

  urlBox.addEventListener('focus', function () { urlBox.select(); });
  document.getElementById('share-close').addEventListener('click', function () { dialog.close(); });
  dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); }); // click outside
  dialog.addEventListener('close', resetCopyButton);
})();
