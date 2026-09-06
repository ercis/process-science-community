# Deploying

The landing page and the join collector run on one VM, under one domain, from
one `docker compose` stack. Caddy serves `../site` as the web root and proxies
`/api/*` to the collector in `../service`.

Same origin is the point: the form posts to `/api/join` on its own host, so
there is no CORS to configure, no third-party form processor, and the personal
data people type in never leaves the machine.

```
browser ──▶ :443 Caddy ──┬── /api/*  ──▶ join-collector:8080 ──▶ SQLite volume
                         └── /*      ──▶ /srv/site  (read-only mount of ../site)
```

## DNS

Point the domain at the VM. Both records, so `www` works too:

```
process-science.org.        A      <VM public IPv4>
www.process-science.org.    A      <VM public IPv4>
```

Add `AAAA` records as well if the VM has a public IPv6 address.

Caddy obtains and renews the Let's Encrypt certificate itself. For that to
work, **ports 80 and 443 must be reachable from the internet** and DNS must
already resolve to the VM. Do the DNS first, then start the stack, or the first
certificate request fails and Caddy backs off before retrying.

Mail is unaffected by this. `MX` records are separate from `A` records, so a
mailbox or forwarder on `process-science.org` coexists with the site.

## First run

```bash
git clone https://github.com/ercis/process-science-community.git
cd process-science-community/deploy
cp .env.example .env
openssl rand -hex 32          # paste into JOIN_EXPORT_TOKEN in .env
docker compose up -d --build
```

`.env` is gitignored. Keep the export token out of the repository.

Check it:

```bash
curl -sI https://process-science.org/ | head -3
curl -s  https://process-science.org/api/healthz
```

Then open the page, submit the form once yourself, and confirm the row is
there. Delete the test row afterwards.

## Updating the page

The site is a read-only bind mount of `../site`, so there is nothing to build
and nothing to restart:

```bash
git pull
```

That is the whole deployment. Caddy picks up the new files immediately;
`assets/` is cached for an hour, so a correction to the people list is visible
within the hour without a hard refresh.

Changing anything in `../service` does need a rebuild:

```bash
docker compose up -d --build join-collector
```

## Getting the submissions out

```bash
curl -H "Authorization: Bearer $JOIN_EXPORT_TOKEN" \
  https://process-science.org/api/admin/submissions.csv -o join.csv
```

The export routes are reachable from the internet and protected by that bearer
token alone, so treat it like a password. It is the only thing standing between
the internet and everybody's contact details. Rotating it is an edit to `.env`
and `docker compose up -d join-collector`.

## Backups

Everything anyone submits lives in one Docker volume, `deploy_join-data`.
Nothing else in this repository is stateful. Back it up:

```bash
docker run --rm -v deploy_join-data:/data -v "$PWD":/out alpine \
  tar czf /out/join-data-$(date +%F).tar.gz -C /data .
```

Put that on a schedule before the form goes in front of an audience. A keynote
QR code can produce every submission you will ever get in one ten-minute burst,
and there is no second copy anywhere.

## Removing someone

The consent line on the form promises people can withdraw and be removed, so
somebody has to be able to act on it:

```bash
docker compose exec join-collector python -c "
import sqlite3; c=sqlite3.connect('/data/join.sqlite3')
print(c.execute(\"DELETE FROM submissions WHERE lower(email)=lower('someone@example.org')\").rowcount)
c.commit()"
```

Agree who owns that before launch.

## Security notes

- The collector publishes no port. Only Caddy reaches it, on the internal
  Docker network.
- It runs as an unprivileged user and writes only to the mounted volume.
- Caddy serves `../site` and nothing else, so `.git` and the service source are
  not reachable. There is a test for this: `curl -i https://process-science.org/.git/config`
  must return 404.
- The `Content-Security-Policy` header in the `Caddyfile` is strict:
  `script-src 'self'`, no `unsafe-inline`. That only holds because every script
  is a file under `site/assets/`. **If you ever add an inline `<script>` or a
  `style` attribute to a page, it will be blocked and the page will break.**
  Put it in `site/assets/app.js` instead.
