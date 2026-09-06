/*
 * Shared behaviour for every page: theme, scroll reveals, the people grid and
 * the platform screenshots. Each piece no-ops when its elements are absent, so
 * the landing page, /join/ and 404.html all load this one file.
 *
 * It lives here rather than inline so the site can be served under a strict
 * Content-Security-Policy with script-src 'self' and no unsafe-inline.
 */

/* theme: follows the system by default, manual override wins and persists */
  (function () {
    var root = document.documentElement;
    var btn = document.getElementById('theme-toggle');
    var stored = null;
    try { stored = localStorage.getItem('psc-theme'); } catch (e) {}
    function systemDark() { return window.matchMedia('(prefers-color-scheme: dark)').matches; }
    function apply(theme) {
      root.classList.add('theme-snap');
      if (theme === 'dark') { root.setAttribute('data-theme', 'dark'); }
      else { root.removeAttribute('data-theme'); }
      if (btn) {
        btn.textContent = theme === 'dark' ? '☼' : '☾';
        btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
      }
      if (window.__updateShots) window.__updateShots();
      requestAnimationFrame(function () {
        requestAnimationFrame(function () { root.classList.remove('theme-snap'); });
      });
    }
    var current = stored || (systemDark() ? 'dark' : 'light');
    apply(current);
    if (btn) btn.addEventListener('click', function () {
      current = current === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('psc-theme', current); } catch (e) {}
      apply(current);
    });
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
      if (!stored) { current = e.matches ? 'dark' : 'light'; apply(current); }
    });
  })();

  /* reveal on scroll */
  (function () {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.querySelectorAll('.reveal').forEach(function (el) { el.classList.add('on'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('on'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    document.querySelectorAll('.reveal').forEach(function (el) { io.observe(el); });
  })();

  /* people: rendered from the JSON block above, so adding someone is a one-line edit.
     The list is long, so it starts collapsed and expands on request. */
  (function () {
    var grid = document.getElementById('people-grid');
    var moreBtn = document.getElementById('people-more');
    var node = document.getElementById('people-data');
    if (!grid || !node) return;
    var people;
    try { people = JSON.parse(node.textContent); } catch (e) { return; }

    var COLLAPSED = 36;
    var expanded = people.length <= COLLAPSED;

    function card(p) {
      var el = document.createElement('div');
      el.className = 'person';
      var av = document.createElement('span');
      av.className = 'pavatar';
      av.setAttribute('aria-hidden', 'true');
      av.textContent = p.initials;
      var who = document.createElement('div');
      who.className = 'who';
      var b = document.createElement('b');
      b.textContent = p.name;
      var s = document.createElement('span');
      s.textContent = p.affiliation;
      who.appendChild(b); who.appendChild(s);
      el.appendChild(av); el.appendChild(who);
      return el;
    }

    function render() {
      var shown = expanded ? people : people.slice(0, COLLAPSED);
      var frag = document.createDocumentFragment();
      shown.forEach(function (p) { frag.appendChild(card(p)); });
      grid.textContent = '';
      grid.appendChild(frag);
      if (people.length > COLLAPSED) {
        moreBtn.hidden = false;
        moreBtn.textContent = expanded ? 'Show fewer' : 'Show all ' + people.length + ' people';
        moreBtn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      }
    }

    if (moreBtn) moreBtn.addEventListener('click', function () {
      expanded = !expanded;
      render();
      if (!expanded) document.getElementById('people').scrollIntoView({ block: 'start' });
      else moreBtn.focus();
    });

    render();

    /* keep the headline count honest: it is derived, never typed in */
    var stat = document.getElementById('stat-people');
    if (stat) stat.textContent = String(people.length);
  })();

/* platform screenshots follow the theme; if one is missing, drop the frame
     rather than showing a broken image */
  (function () {
    var shots = Array.prototype.slice.call(document.querySelectorAll('.pshot img[data-shot]'));
    if (!shots.length) return;
    shots.forEach(function (img) {
      img.addEventListener('error', function () {
        var frame = img.closest('.pshot');
        if (frame) frame.hidden = true;
      });
    });
    window.__updateShots = function () {
      var dark = document.documentElement.getAttribute('data-theme') === 'dark';
      shots.forEach(function (img) {
        var next = img.dataset.shot + (dark ? '-dark' : '-light') + '.webp';
        if (img.getAttribute('src') !== next) img.setAttribute('src', next);
      });
    };
    window.__updateShots();
  })();
