/* =======================================================================
   Join form. Shared by the landing page (#join) and /join/.

   FORM_ENDPOINT is where submissions go. It is a same-origin path, so the
   browser sends no cross-origin request, there is no CORS to configure, and
   no third party sits in the path: Caddy on the VM proxies /api/* to the
   collector in ../service. See deploy/README.md.

   Set it to null to fall back to opening a pre-filled email instead. That
   fallback depends on the visitor having a working mail client, so it is not
   good enough for a QR code scanned on a phone in a keynote audience. It is
   here as a safety net, not as a plan.
   ======================================================================= */
var FORM_ENDPOINT = "/api/join";

// Shown when a submission fails, and used by the mailto fallback. This is the
// only place the contact address appears in the JavaScript; the pages carry it
// in the footer and next to the people list.
var CONTACT_EMAIL = "zimmermann.tobias@uni-muenster.de";

(function () {
  var form = document.getElementById('joinForm');
  if (!form) return;
  var errBox = document.getElementById('err');
  var btn = document.getElementById('submitBtn');
  var formView = document.getElementById('formView');
  var doneView = document.getElementById('doneView');

  function fail(msg, focusId) {
    errBox.textContent = msg;
    errBox.classList.add('show');
    var el = focusId && document.getElementById(focusId);
    if (el) el.focus({ preventScroll: false });
  }
  function clearFail() { errBox.classList.remove('show'); errBox.textContent = ''; }

  function collect() {
    var fd = new FormData(form);
    return {
      name: (fd.get('name') || '').trim(),
      email: (fd.get('email') || '').trim(),
      organisation: (fd.get('organisation') || '').trim(),
      role: fd.get('role') || '',
      interest: fd.getAll('interest').join(', '),
      about: (fd.get('about') || '').trim(),
      website: fd.get('website') || '',   // honeypot, must stay empty
      consent: fd.get('consent') ? 'yes' : 'no',
      source: document.body.dataset.source || 'landing',
      submitted_at: new Date().toISOString()
    };
  }

  /* One clear error at a time, in the order the fields appear. */
  function validate(d) {
    if (!d.name) return ['Please tell us your name.', 'f-name'];
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) return ['Please enter a valid email address.', 'f-email'];
    if (!d.organisation) return ['Please tell us your institution or organisation.', 'f-org'];
    if (!d.role) return ['Please choose your role.', 'f-role'];
    if (!d.interest) return ['Please choose at least one thing you would like to do.', 'f-consent'];
    if (d.consent !== 'yes') return ['Please tick the consent box so we may reply to you.', 'f-consent'];
    return null;
  }

  function showDone() {
    formView.style.display = 'none';
    doneView.classList.add('show');
    doneView.focus();
    doneView.scrollIntoView({ block: 'center' });
  }

  function mailtoFallback(d) {
    var body =
      'Name: ' + d.name + '\n' +
      'Email: ' + d.email + '\n' +
      'Institution: ' + d.organisation + '\n' +
      'Role: ' + d.role + '\n' +
      'Would like to: ' + d.interest + '\n\n' +
      'More:\n' + (d.about || '-') + '\n\n' +
      'Consent to be contacted: ' + d.consent + '\n';
    window.location.href = 'mailto:' + CONTACT_EMAIL +
      '?subject=' + encodeURIComponent('Join the Process Science Community') +
      '&body=' + encodeURIComponent(body);
    showDone();
  }

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearFail();
    var data = collect();
    var problem = validate(data);
    if (problem) { fail(problem[0], problem[1]); return; }
    if (!FORM_ENDPOINT) { mailtoFallback(data); return; }

    btn.disabled = true;
    btn.textContent = 'Sending...';
    fetch(FORM_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify(data)
    }).then(function (res) {
      if (!res.ok) throw new Error('status ' + res.status);
      showDone();
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = 'Join the community';
      fail('Sorry, that did not go through. Please try again, or email us directly at ' + CONTACT_EMAIL + '.');
    });
  });
})();
