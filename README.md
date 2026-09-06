# Process Science Community

The landing page for the Process Science Community, served by GitHub Pages at
**https://process-science.org**.

It replaces [process-science.net](https://process-science.net/), the site built
in 2021 under an Erasmus+ grant, and adds the two community platforms that did
not exist then plus a join form.

Static HTML, CSS and vanilla JavaScript. No build step, no framework, no npm
install, no runtime requests to anyone. Edit, push, done.

```
index.html            the landing page, including the people data
join/index.html       the same join form on its own URL, /join/  (the QR target)
assets/styles.css     the whole design system, shared by all three pages
assets/join.js        form validation and submission, shared by both join forms
assets/icon.svg       favicon
assets/*.webp         platform screenshots, light and dark
404.html  robots.txt  sitemap.xml  CNAME
service/              optional self-hosted collector for the join form
keynote/              QR codes for the closing slide
```

## Where this repository should live

It is in `ercis` for now, next to
[`ercis/MATE`](https://github.com/ercis/MATE), because that org already exists
and Pages with a custom domain works there today.

**The intended home is a dedicated Process Science Community GitHub org**, to be
created later, with MATE and the teaching platform moving into it as well. When
that happens, transfer this repository rather than re-creating it: GitHub keeps
the redirects, and every internal link on the site is relative, so nothing on
the page breaks. The only things to redo are the `www` DNS record (below) and
the Pages source setting.

## Preview locally

```bash
python3 -m http.server -d . 8099
```

Then open http://localhost:8099. The page also works opened straight from disk
as a `file://` URL, which is why the people data is embedded in `index.html`
rather than fetched from a separate JSON file. (`404.html` is the exception: it
uses root-absolute asset paths, because Pages serves it for a miss at any depth.)

## Deploying

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) publishes the
repository root on every push to `main`.

One-time setup, in this order:

1. **Settings -> Pages -> Build and deployment -> Source: "GitHub Actions".**
   The repository has to be public.
2. Set the DNS records below at the registrar for `process-science.org`.
3. **Settings -> Pages -> Custom domain:** enter `process-science.org`. The
   `CNAME` file already holds it, so this should already be filled in.
4. Wait for the certificate to be issued, then tick **Enforce HTTPS** on the
   same settings page. It stays greyed out until the certificate is ready,
   which is usually minutes but can take up to 24 hours.

### DNS records

For the apex domain `process-science.org`, four `A` records:

```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

And, if you also want IPv6, four `AAAA` records:

```
2606:50c0:8000::153
2606:50c0:8001::153
2606:50c0:8002::153
2606:50c0:8003::153
```

For `www.process-science.org`, one `CNAME` record pointing at:

```
ercis.github.io
```

If the repository moves to a different owner later, that `CNAME` value changes
to `<new-owner>.github.io`. The `A` records do not change.

## Editing the page

### People

The people list is a JSON block at the bottom of `index.html`, marked
`<script type="application/json" id="people-data">`. One person per line:

```json
{"name":"Ada Lovelace","affiliation":"Analytical Engine Group","initials":"AL"}
```

Adding someone is a one-line edit and never touches layout. The list is sorted
by surname; keep it that way. The headline count in the stats row is derived
from this data at runtime, so it can never disagree with the list.

`initials` is the first letter of the given name plus the first letter of the
surname, ignoring particles: "Wil van der Aalst" gives `WA`. People the previous
site listed by first name only keep a single letter.

### The join form

`FORM_ENDPOINT` at the top of `assets/join.js` is the one thing to change to
make submissions land somewhere. It POSTs a flat JSON object.

It ships as `null`, which makes the form fall back to opening a pre-filled
email. **That fallback is not good enough for a QR code scanned on a phone in a
keynote audience**: it depends on the visitor having a working mail client, and
on a shared or locked-down phone it does nothing at all. Set a real endpoint.

**Recommended: the collector in [`service/`](service/).** A small FastAPI
service you run next to the MATE API on the ERCIS VM. It reuses the live
`mate.uni-muenster.de` host and certificate, so it needs no new DNS record and
no change at the university edge proxy. Personal data never leaves an ERCIS
machine, which keeps a data processing agreement off the critical path.
See [`service/README.md`](service/README.md).

**Fallback if the VM cannot be ready in time:**
[Formspree](https://formspree.io) or [Basin](https://usebasin.com). Create a
form, copy the endpoint, paste it into `FORM_ENDPOINT`. Both accept exactly the
JSON this form sends. Note that both are US processors handling personal data
of people in the EU, so treat it as a temporary measure and tell people in the
privacy notice.

**Tally does not work here**, despite being an obvious candidate. Tally only
offers outbound webhooks (it calls your server after someone submits a
*Tally-hosted* form) and an API that needs a secret key, which cannot ship in a
public static page. The only way to use Tally would be to embed its own form,
which would break the no-external-requests rule and would not match the design.

The form markup exists twice, in `index.html` and in `join/index.html`, because
the two pages need it in different surroundings. The validation and submission
logic exists once, in `assets/join.js`. If you change a field, change it in
both HTML files and check the collector in the JS and the model in
`service/app/main.py` still match.

The form carries a honeypot field named `website`. It is hidden from people and
from screen readers; bots fill it in. Leave it alone.

## Conventions

- British spelling throughout.
- No em dashes anywhere in the copy. Use a colon, a comma or a full stop.
- No external requests at runtime: no CDN, no web fonts, no analytics, no
  trackers. That is also why there is no cookie banner: there is nothing to
  consent to.
- Every outbound link and every conference date on the page was checked against
  the organisers' own pages in September 2026. Conference dates drift; re-check
  before a relaunch.
- The `--muted` colour is one shade darker than the MATE landing page's, because
  MATE's value is 3.4:1 on white and fails WCAG AA for body text. Everything
  else in the design system is MATE's, unchanged.

## Licence

MIT, see [LICENSE](LICENSE).

The page was originally created with the support of the Erasmus+ programme of
the European Union, grant 2019-1-LI01-KA203-000169.
