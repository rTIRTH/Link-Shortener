// "Go back" on the preview page: return to where the visitor came from, if there is a page to go to.
(function () {
  document.addEventListener('click', function (e) {
    var link = e.target.closest ? e.target.closest('[data-back]') : null;
    if (!link || window.history.length < 2) return; // no history: the link goes to the home page
    e.preventDefault();
    window.history.back();
  });
})();
