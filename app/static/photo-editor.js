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
  var zoomLabel = $('pd-zoom-val'), angleLabel = $('pd-angle-val'), cameraStatus = $('pd-camera-status');
  var saveBtn = $('pd-save'), errorBox = $('pd-error'), preview = $('pd-preview');
  var ctx = canvas.getContext('2d');
  var previewCtx = preview ? preview.getContext('2d') : null;

  var SIZE = canvas.width;              // the editing canvas is square
  var R = Math.round(SIZE * 0.43);      // radius of the circle that gets saved
  var OUT = 256;                        // size of the saved picture
  var MAX_SIDE = 1600;                  // bigger photos are shrunk first, to stay fast on phones
  var MIN_ZOOM = 1, MAX_ZOOM = 4;

  var source = null, sw = 0, sh = 0;    // the picture being edited and its size
  var zoom = 1, angle = 0, off = { x: 0, y: 0 };  // off = where the picture's centre sits vs the circle's
  var stream = null, saveLabel = saveBtn.textContent;

  // ----- the maths (plain functions, so they can be tested) -----
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

  // Draw the picture into any square canvas. k = how much bigger than the editing canvas it is.
  function paint(c, size, k) {
    c.save();
    c.translate(size / 2 + off.x * k, size / 2 + off.y * k);
    c.rotate(angle * Math.PI / 180);
    c.scale(scale() * k, scale() * k);
    c.drawImage(source, -sw / 2, -sh / 2);
    c.restore();
  }
  function draw() {
    ctx.clearRect(0, 0, SIZE, SIZE);
    if (!source) return;
    paint(ctx, SIZE, 1);
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
    if (previewCtx) {                                      // a small live copy of what will be saved
      var p = preview.width;
      previewCtx.clearRect(0, 0, p, p);
      previewCtx.fillStyle = '#fff';
      previewCtx.fillRect(0, 0, p, p);
      paint(previewCtx, p, p / (2 * R));
    }
  }
  function update() {
    refit();
    zoomInput.value = Math.round(zoom * 100);
    angleInput.value = Math.round(angle);
    if (zoomLabel) zoomLabel.textContent = Math.round(zoom * 100) + '%';
    if (angleLabel) angleLabel.textContent = Math.round(angle) + '\u00b0';
    draw();
  }

  // ----- steps and messages -----
  function show(name) { Object.keys(steps).forEach(function (k) { steps[k].hidden = k !== name; }); }
  function showError(message) { errorBox.textContent = message || ''; errorBox.hidden = !message; }
  function stopCamera() {
    if (stream) { stream.getTracks().forEach(function (t) { t.stop(); }); stream = null; }
    video.srcObject = null;
    if (cameraStatus) cameraStatus.hidden = false;
  }
  function reset() {
    stopCamera();
    source = null;
    saveBtn.disabled = false;
    saveBtn.classList.remove('is-busy');
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
  function invalidPhoto() { return tr('photo_invalid', 'That file is not a valid photo. Please use a JPEG, PNG or WebP image.'); }
  function fromFile(file) {
    if (!file) return;
    if (!/^image\//.test(file.type)) { showError(invalidPhoto()); return; }
    var url = URL.createObjectURL(file), img = new Image();
    img.onload = function () { URL.revokeObjectURL(url); setSource(img, img.naturalWidth, img.naturalHeight); };
    img.onerror = function () { URL.revokeObjectURL(url); showError(invalidPhoto()); };
    img.src = url;
  }
  function pickFile(withCamera) {
    if (withCamera) fileInput.setAttribute('capture', 'user'); else fileInput.removeAttribute('capture');
    fileInput.value = '';
    fileInput.click();
    fileInput.removeAttribute('capture');
  }

  // ----- camera -----
  function cameraMessage(err) {
    var name = err && err.name;
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError' || name === 'SecurityError') {
      return tr('camera_blocked', 'Camera access is blocked. Click the camera icon in the address bar, choose Allow, then try again.');
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return tr('camera_missing', 'No camera was found on this device.');
    }
    if (name === 'NotReadableError' || name === 'TrackStartError' || name === 'AbortError') {
      return tr('camera_busy', 'Your camera is being used by another app. Close it and try again.');
    }
    return tr('photo_camera_failed', 'We could not open the camera. You can upload a photo instead.');
  }
  function onPhone() { return !!(window.matchMedia && window.matchMedia('(pointer: coarse)').matches); }
  function openCamera() {
    showError('');
    function failed(err) {
      stopCamera();
      show('choose');
      showError(cameraMessage(err));
      if (onPhone()) pickFile(true);        // phones can hand over to the camera app; laptops just get the reason
    }
    var devices = navigator.mediaDevices;
    if (!devices || !devices.getUserMedia) { failed(null); return; }
    devices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      .catch(function (err) {
        if (err && err.name === 'OverconstrainedError') return devices.getUserMedia({ video: true, audio: false });
        throw err;
      })
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        show('camera');
        var played = video.play && video.play();
        if (played && played.catch) played.catch(function () { /* autoplay handles it */ });
      })
      .catch(failed);
  }
  function cameraReady() { if (cameraStatus) cameraStatus.hidden = true; }
  video.addEventListener('loadedmetadata', cameraReady);
  video.addEventListener('playing', cameraReady);
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
  function setZoom(z) { zoom = clamp(z, MIN_ZOOM, MAX_ZOOM); update(); }

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
      update();
    } else if (count() === 2 && pinch) {
      setZoom(pinch.z * spread() / pinch.d);
    }
  });
  function release(e) { delete pointers[e.pointerId]; pinch = null; }
  canvas.addEventListener('pointerup', release);
  canvas.addEventListener('pointercancel', release);
  canvas.addEventListener('wheel', function (e) {
    if (!source) return;
    e.preventDefault();
    setZoom(zoom * Math.exp(-e.deltaY * 0.0015));
  }, { passive: false });
  zoomInput.addEventListener('input', function () { setZoom(zoomInput.value / 100); });
  angleInput.addEventListener('input', function () { angle = normaliseAngle(+angleInput.value); update(); });
  $('pd-left').addEventListener('click', function () { angle = normaliseAngle(angle - 90); update(); });
  $('pd-right').addEventListener('click', function () { angle = normaliseAngle(angle + 90); update(); });
  if ($('pd-zoom-in')) $('pd-zoom-in').addEventListener('click', function () { setZoom(zoom + 0.25); });
  if ($('pd-zoom-out')) $('pd-zoom-out').addEventListener('click', function () { setZoom(zoom - 0.25); });
  if ($('pd-reset')) $('pd-reset').addEventListener('click', function () { zoom = 1; angle = 0; off = { x: 0, y: 0 }; update(); });

  // ----- saving -----
  function exportBlob(done) {
    var out = document.createElement('canvas');
    out.width = out.height = OUT;
    var c = out.getContext('2d');
    c.fillStyle = '#fff';
    c.fillRect(0, 0, OUT, OUT);
    paint(c, OUT, OUT / (2 * R));
    out.toBlob(done, 'image/jpeg', 0.9);
  }
  function busy(on) {
    saveBtn.disabled = on;
    saveBtn.classList.toggle('is-busy', on);
    saveBtn.textContent = on ? tr('photo_saving', 'Saving…') : saveLabel;
  }
  function save() {
    if (!source) { showError(tr('photo_choose', 'Please choose a photo first.')); return; }
    busy(true);
    function fail(message) { busy(false); showError(message || tr('photo_failed', 'The photo could not be saved. Please try again.')); }
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

  // ----- dropping a file onto the pop-up -----
  var dragDepth = 0;
  dialog.addEventListener('dragenter', function (e) { e.preventDefault(); dragDepth++; dialog.classList.add('is-dragging'); });
  dialog.addEventListener('dragover', function (e) { e.preventDefault(); });
  dialog.addEventListener('dragleave', function () { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) dialog.classList.remove('is-dragging'); });
  dialog.addEventListener('drop', function (e) {
    e.preventDefault();
    dragDepth = 0;
    dialog.classList.remove('is-dragging');
    var files = e.dataTransfer && e.dataTransfer.files;
    if (files && files[0]) { stopCamera(); fromFile(files[0]); }
  });

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
