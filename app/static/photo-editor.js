/* Profile photo editor: choose or take a photo, move / zoom / rotate it inside a circle, save.
 * Only the circle's contents are saved. The server re-checks and re-encodes the picture. */
(function () {
  'use strict';

  var dialog = document.getElementById('photo-dialog');
  var openBtn = document.getElementById('photo-open');
  if (!dialog || !openBtn) return;

  var DATA = {};
  try { DATA = JSON.parse(document.getElementById('i18n-data').textContent) || {}; } catch (e) { DATA = {}; }
  var UI = DATA.ui || {};
  function tr(key, fallback) { return UI[key] || fallback; }
  function $(id) { return document.getElementById(id); }

  var steps = { choose: $('pd-choose'), camera: $('pd-camera-view'), edit: $('pd-edit') };
  var fileInput = $('pd-file'), video = $('pd-video'), canvas = $('pd-canvas');
  var zoomInput = $('pd-zoom'), angleInput = $('pd-angle');
  var saveBtn = $('pd-save'), errorBox = $('pd-error');
  var ctx = canvas.getContext('2d');

  var SIZE = canvas.width;              // the preview is square
  var R = Math.round(SIZE * 0.43);      // radius of the circle that gets saved
  var OUT = 256;                        // size of the saved picture
  var MAX_SIDE = 1600;                  // bigger photos are shrunk first, to stay fast on phones
  var MIN_ZOOM = 1, MAX_ZOOM = 4;

  var source = null, sw = 0, sh = 0;    // the picture being edited and its size
  var zoom = 1, angle = 0, off = { x: 0, y: 0 };  // off = where the picture's centre sits vs the circle's
  var stream = null, saveLabel = saveBtn.textContent;

  // ----- the maths (kept as plain functions so they can be tested) -----
  function coverScale(w, h, r) { return (2 * r) / Math.min(w, h); }   // smallest scale that fills the circle

  // Keep the circle fully inside the picture, whatever its rotation.
  function clampOffset(o, w, h, scale, deg, r) {
    var rad = deg * Math.PI / 180, cos = Math.cos(rad), sin = Math.sin(rad);
    var vx = -o.x, vy = -o.y;                              // circle centre, seen from the picture's centre
    var lx = vx * cos + vy * sin, ly = -vx * sin + vy * cos;   // ... in the picture's own (rotated) axes
    var mx = Math.max(0, w * scale / 2 - r), my = Math.max(0, h * scale / 2 - r);
    lx = Math.min(mx, Math.max(-mx, lx));
    ly = Math.min(my, Math.max(-my, ly));
    return { x: -(lx * cos - ly * sin), y: -(lx * sin + ly * cos) };
  }
  function normaliseAngle(a) { return ((a + 180) % 360 + 360) % 360 - 180; }
  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  window.__photoMath = { coverScale: coverScale, clampOffset: clampOffset, normaliseAngle: normaliseAngle };

  function scale() { return coverScale(sw, sh, R) * zoom; }
  function refit() { off = clampOffset(off, sw, sh, scale(), angle, R); }

  function draw() {
    ctx.clearRect(0, 0, SIZE, SIZE);
    if (!source) return;
    ctx.save();
    ctx.translate(SIZE / 2 + off.x, SIZE / 2 + off.y);
    ctx.rotate(angle * Math.PI / 180);
    ctx.scale(scale(), scale());
    ctx.drawImage(source, -sw / 2, -sh / 2);
    ctx.restore();
    ctx.save();                                            // darken everything outside the circle
    ctx.fillStyle = 'rgba(0,0,0,0.55)';
    ctx.beginPath();
    ctx.rect(0, 0, SIZE, SIZE);
    ctx.arc(SIZE / 2, SIZE / 2, R, 0, Math.PI * 2, true);
    ctx.fill('evenodd');
    ctx.strokeStyle = 'rgba(255,255,255,0.9)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(SIZE / 2, SIZE / 2, R, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }
  function update() {
    refit();
    zoomInput.value = Math.round(zoom * 100);
    angleInput.value = Math.round(angle);
    draw();
  }

  // ----- steps and messages -----
  function show(name) {
    Object.keys(steps).forEach(function (k) { steps[k].hidden = k !== name; });
  }
  function showError(message) { errorBox.textContent = message || ''; errorBox.hidden = !message; }
  function stopCamera() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    video.srcObject = null;
  }
  function reset() {
    stopCamera();
    source = null;
    saveBtn.disabled = false;
    saveBtn.textContent = saveLabel;
    showError('');
    show('choose');
  }

  // ----- getting a picture -----
  function setSource(element, w, h) {
    var k = Math.min(1, MAX_SIDE / Math.max(w, h));
    if (k < 1) {
      var small = document.createElement('canvas');
      small.width = Math.round(w * k);
      small.height = Math.round(h * k);
      small.getContext('2d').drawImage(element, 0, 0, small.width, small.height);
      element = small; w = small.width; h = small.height;
    }
    source = element; sw = w; sh = h;
    zoom = 1; angle = 0; off = { x: 0, y: 0 };
    showError('');
    show('edit');
    update();
  }
  function fromFile(file) {
    if (!file) return;
    if (!/^image\//.test(file.type)) { showError(tr('photo_invalid', 'That file is not a valid photo. Please use a JPEG, PNG or WebP image.')); return; }
    var url = URL.createObjectURL(file), img = new Image();
    img.onload = function () { URL.revokeObjectURL(url); setSource(img, img.naturalWidth, img.naturalHeight); };
    img.onerror = function () { URL.revokeObjectURL(url); showError(tr('photo_invalid', 'That file is not a valid photo. Please use a JPEG, PNG or WebP image.')); };
    img.src = url;
  }
  function pickFile(withCamera) {
    if (withCamera) fileInput.setAttribute('capture', 'user'); else fileInput.removeAttribute('capture');
    fileInput.value = '';
    fileInput.click();
    fileInput.removeAttribute('capture');
  }
  function openCamera() {
    showError('');
    function fallback() { showError(tr('photo_camera_failed', 'We could not open the camera. You can upload a photo instead.')); pickFile(true); }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) { fallback(); return; }
    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      .then(function (s) { stream = s; video.srcObject = s; show('camera'); })
      .catch(fallback);
  }
  function capture() {
    var w = video.videoWidth, h = video.videoHeight;
    if (!w || !h) return;
    var c = document.createElement('canvas');
    c.width = w; c.height = h;
    c.getContext('2d').drawImage(video, 0, 0, w, h);
    stopCamera();
    setSource(c, w, h);
  }

  // ----- moving, zooming, rotating -----
  var pointers = {}, pinch = null;
  function count() { return Object.keys(pointers).length; }
  function spread() {
    var p = Object.keys(pointers).map(function (k) { return pointers[k]; });
    return Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y) || 1;
  }
  function pixelRatio() { var w = canvas.getBoundingClientRect().width; return w ? SIZE / w : 1; }

  canvas.addEventListener('pointerdown', function (e) {
    if (!source) return;
    try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* not supported */ }
    pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
    pinch = count() === 2 ? { d: spread(), z: zoom } : null;
  });
  canvas.addEventListener('pointermove', function (e) {
    var p = pointers[e.pointerId];
    if (!p || !source) return;
    var dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    if (count() === 1) {
      var k = pixelRatio();
      off = { x: off.x + dx * k, y: off.y + dy * k };
    } else if (count() === 2 && pinch) {
      zoom = clamp(pinch.z * spread() / pinch.d, MIN_ZOOM, MAX_ZOOM);
    }
    update();
  });
  function release(e) { delete pointers[e.pointerId]; pinch = null; }
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('wheel', function (e) {
    if (!source) return;
    e.preventDefault();
    zoom = clamp(zoom * Math.exp(-e.deltaY * 0.0015), MIN_ZOOM, MAX_ZOOM);
    update();
  }, { passive: false });
  zoomInput.addEventListener('input', function () { zoom = clamp(zoomInput.value / 100, MIN_ZOOM, MAX_ZOOM); update(); });
  angleInput.addEventListener('input', function () { angle = normaliseAngle(+angleInput.value); update(); });
  $('pd-left').addEventListener('click', function () { angle = normaliseAngle(angle - 90); update(); });
  $('pd-right').addEventListener('click', function () { angle = normaliseAngle(angle + 90); update(); });

  // ----- saving -----
  function exportBlob(done) {
    var out = document.createElement('canvas');
    out.width = out.height = OUT;
    var c = out.getContext('2d'), k = OUT / (2 * R);
    c.fillStyle = '#fff';
    c.fillRect(0, 0, OUT, OUT);
    c.translate(OUT / 2 + off.x * k, OUT / 2 + off.y * k);
    c.rotate(angle * Math.PI / 180);
    c.scale(scale() * k, scale() * k);
    c.drawImage(source, -sw / 2, -sh / 2);
    out.toBlob(done, 'image/jpeg', 0.9);
  }
  function save() {
    if (!source) { showError(tr('photo_choose', 'Please choose a photo first.')); return; }
    saveBtn.disabled = true;
    saveBtn.textContent = tr('photo_saving', 'Saving…');
    function fail(message) {
      saveBtn.disabled = false;
      saveBtn.textContent = saveLabel;
      showError(message || tr('photo_failed', 'The photo could not be saved. Please try again.'));
    }
    exportBlob(function (blob) {
      if (!blob) { fail(); return; }
      var form = new FormData();
      form.append('photo', blob, 'photo.jpg');
      fetch('/account/photo', { method: 'POST', body: form, credentials: 'same-origin' })
        .then(function (r) {
          return r.json().catch(function () { return {}; }).then(function (body) {
            if (r.ok && body.ok) { window.location.reload(); } else { fail(body.error); }
          });
        })
        .catch(function () { fail(); });
    });
  }

  // ----- wiring -----
  function closeDialog() { if (dialog.close) dialog.close(); else dialog.removeAttribute('open'); }
  openBtn.addEventListener('click', function () {
    reset();
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute('open', '');
  });
  dialog.addEventListener('close', reset);
  Array.prototype.forEach.call(dialog.querySelectorAll('[data-pd-close]'), function (b) { b.addEventListener('click', closeDialog); });
  $('pd-upload').addEventListener('click', function () { pickFile(false); });
  $('pd-camera').addEventListener('click', openCamera);
  $('pd-camera-back').addEventListener('click', reset);
  $('pd-capture').addEventListener('click', capture);
  $('pd-another').addEventListener('click', reset);
  $('pd-save').addEventListener('click', save);
  fileInput.addEventListener('change', function () { fromFile(fileInput.files && fileInput.files[0]); });
})();
