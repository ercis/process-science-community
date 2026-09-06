# Process Science Community

The landing page for the Process Science Community, served at
**https://process-science.org**.

It replaces [process-science.net](https://process-science.net/), the site built
in 2021 under an Erasmus+ grant, and adds the two community platforms that did
not exist then plus a join form.

The page is static HTML, CSS and vanilla JavaScript: no build step, no
framework, no npm install, no runtime request to anyone. The join form posts to
a small FastAPI collector on the same origin, so nobody's contact details leave
the machine.

```
site/                 the static site, served as the web root
  index.html          the landing page, including the people data
  join/index.html     the same join form on its own URL, /join/  (the QR target)
  assets/styles.css   the design system, shared by all three pages
  assets/app.js       theme, scroll reveals, people grid, platform screenshots
  assets/join.js      form validation and submission
  404.html  robots.txt  sitemap.xml
service/              the join collector (FastAPI + SQLite)
deploy/               Caddy + docker compose, the whole VM stack
  submissions.sh      read the join submissions
  auto-update.sh      pull and apply on a timer, like GitHub Pages
keynote/              QR code for the closing slide
```

## Deploying

Everything runs on one VM: see **[deploy/README.md](deploy/README.md)** for DNS,
first run, updating, backups and the export token.

Updating the page after the first deploy is `git pull` on the VM. There is
nothing to build.

## Where this repository should live

It is in `ercis` for now, next to [`ercis/MATE`](https://github.com/ercis/MATE).

**The intended home is a dedicated Process Science Community GitHub org**, to be
created later, with MATE and the teaching platform moving into it as well. When
that happens, transfer this repository rather than re-creating it: GitHub keeps
the redirects, every internal link on the site is relative, and the deployment
only needs its remote updated.

## Preview locally

```bash
python3 -m http.server -d site 8099
```

Then open http://localhost:8099. The form will not submit against that server,
because there is no `/api` behind it: to exercise the whole thing, run the real
stack from `deploy/`.

## Editing the page

### People

The people list is a JSON block at the bottom of `site/index.html`, marked
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

`FORM_ENDPOINT` at the top of `site/assets/join.js` is `/api/join`, a
same-origin path that Caddy proxies to the collector. Setting it to `null`
makes the form fall back to opening a pre-filled email instead, which is a
safety net rather than a plan: it depends on the visitor having a working mail
client, and on a locked-down phone it does nothing at all.

The form markup exists twice, in `site/index.html` and in
`site/join/index.html`, because the two pages need it in different
surroundings. The validation and submission logic exists once, in
`site/assets/join.js`. If you change a field, change it in both HTML files and
check the collector in the JS and the model in `service/app/main.py` still
match.

The form carries a honeypot field named `website`. It is hidden from people and
from screen readers; bots fill it in, and the collector discards those
submissions after answering them normally. Leave it alone.

**Hosted form services were considered and rejected.** Tally cannot do this at
all: it offers outbound webhooks and a key-authenticated API, neither of which
can receive a POST from a public static page. Formspree and Basin can, but both
are US processors handling personal data of people in the EU, which puts a data
processing agreement on the critical path. Self-hosting avoids the question.

### The contact address

It appears in four places: `CONTACT_EMAIL` in `site/assets/join.js`, the footer
of `site/index.html` and `site/join/index.html`, and the "correct or remove my
entry" line next to the people list. Change all four together.

## Conventions

- British spelling throughout.
- No em dashes anywhere in the copy. Use a colon, a comma or a full stop.
- No external requests at runtime: no CDN, no web fonts, no analytics, no
  trackers. That is also why there is no cookie banner: there is nothing to
  consent to. The `Content-Security-Policy` in `deploy/Caddyfile` enforces it,
  which is why **no page may contain an inline `<script>` or `style`
  attribute**. Put script in `site/assets/app.js`.
- Every outbound link and every conference date on the page was checked against
  the organisers' own pages in September 2026. Conference dates drift; re-check
  before a relaunch.
- The design system is the MATE landing page's
  ([`ercis/MATE`](https://github.com/ercis/MATE), `landing/`), so the two read
  as siblings. One deliberate deviation: `--muted` is a shade darker here,
  because MATE's value is 3.4:1 on white and fails WCAG AA for body text.

## Licence

MIT, see [LICENSE](LICENSE).
