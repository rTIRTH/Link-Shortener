// Tag chips under a "Tags" box: click one to add it to the box (or remove it again).
(function () {
  function names(input) {
    return input.value.split(',').map(function (t) { return t.trim().toLowerCase(); })
      .filter(function (t) { return t; });
  }
  function sync(input) {
    var on = names(input);
    document.querySelectorAll('[data-tag-pick][data-target="' + input.id + '"]').forEach(function (chip) {
      var active = on.indexOf(chip.getAttribute('data-tag-pick')) !== -1;
      chip.classList.toggle('on', active);
      chip.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }
  document.addEventListener('click', function (e) {
    var chip = e.target.closest ? e.target.closest('[data-tag-pick]') : null;
    if (!chip) return;
    var input = document.getElementById(chip.getAttribute('data-target'));
    if (!input || input.disabled) return;
    var name = chip.getAttribute('data-tag-pick');
    var list = names(input);
    var at = list.indexOf(name);
    if (at === -1) list.push(name); else list.splice(at, 1);
    input.value = list.join(', ');
    sync(input);
  });
  document.addEventListener('input', function (e) {
    if (e.target && e.target.hasAttribute && e.target.hasAttribute('data-tag-input')) sync(e.target);
  });
  // Enter in the "Tag selected" box means "Add tags". Without this the browser would press the first
  // button of the toolbar form, which is "Delete selected".
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Enter' || !e.target || !e.target.hasAttribute || !e.target.hasAttribute('data-bulk-tags')) return;
    e.preventDefault();
    var add = document.getElementById('bulk-tag-add');
    if (add) add.click();
  });
  document.querySelectorAll('[data-tag-input]').forEach(sync);
})();
