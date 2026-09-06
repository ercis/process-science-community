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

## DNS (Strato)

The domain is at Strato. In the Kunden-Login: **Domains → Domainverwaltung →**
the gear icon next to `process-science.org` **→ DNS** tab.

Set two things, and delete or repoint a third:

| Record | Strato control | Value |
| --- | --- | --- |
| `A` | **A-Record verwalten → Eigene IP-Adresse** | the VM's public IPv4 |
| `AAAA` | **AAAA-Record verwalten** | the VM's public IPv6, **or remove the record** |
| `MX` | **MX-Record verwalten** | **do not touch** |

Save each with **Einstellungen übernehmen**.

### The AAAA record will break the certificate if you forget it

This is the trap, and it is not hypothetical: it happened during testing.

Out of the box Strato publishes **both** an A and an AAAA record pointing at
its own parking servers:

```
process-science.org.  A     217.160.0.80
process-science.org.  AAAA  2001:8d8:100f:f000::200
```

Let's Encrypt resolves AAAA **before** A. If you change only the A record, the
validation request goes to Strato over IPv6, gets Strato's parking page instead
of Caddy's challenge response, and the certificate fails, with an error that
looks like DNS has not propagated:

```
Invalid response from http://process-science.org/.well-known/acme-challenge/...: 204
```

So either point the AAAA record at the VM's IPv6 address (Hetzner gives every
server one, usually the `::1` of its assigned `/64`) or delete the AAAA record
entirely. Do not leave Strato's.

### www

`www.process-science.org` is already a CNAME to the apex, so it follows the A
record automatically and needs no separate entry. Confirm after the change:

```bash
dig +short process-science.org A
dig +short process-science.org AAAA
dig +short www.process-science.org
dig +short process-science.org MX      # must still be smtpin.rzone.de
```

Wait until the first two return the VM's addresses before starting the stack.

### Mail keeps working

The `MX` record is managed separately from the `A` record at Strato, so
repointing the site does not affect `info@`, `contact@` or `hello@`. The MX
must stay `5 smtpin.rzone.de`. If it ever changes, the forwarding is broken.

## Firewall

The VM needs three ports reachable: 22, 80 and 443. **80 is not optional**,
even though the site is HTTPS only: Let's Encrypt validates over port 80, and
Caddy uses it to redirect visitors to HTTPS.

If you added a Hetzner Cloud Firewall, allow those three inbound (Cloud Console
→ Firewalls). A stock Hetzner image has no local firewall active; if you enabled
`ufw` yourself:

```bash
sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
```

Note that Docker publishes ports by writing its own iptables rules, which
bypass `ufw`. Do not rely on `ufw` alone to keep something private: the
collector is protected by publishing no port at all, not by a firewall rule.

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

Watch the certificate being issued. This is the step that fails if DNS is
wrong, and the log says so plainly:

```bash
docker compose logs -f caddy
```

Look for `certificate obtained successfully`. If you instead see
`challenge failed` with an IPv6 address in it, the AAAA record is still
pointing at Strato: fix it and run `docker compose restart caddy`.

Then check it end to end:

```bash
curl -sI  https://process-science.org/            | head -3   # 200, and a real certificate
curl -s   https://process-science.org/api/healthz             # {"status":"ok"}
curl -sI  http://process-science.org/             | head -3   # 308 to https
curl -sI  https://www.process-science.org/        | head -3   # 301 to the apex
curl -sI  https://process-science.org/.git/config | head -1   # 404, never 200
```

Then open the page, submit the form once yourself, and confirm the row is
there. Delete the test row afterwards.

### If the certificate does not come

Caddy retries with a growing backoff, so you do not need to restart in a loop.
Check, in this order:

1. `dig +short process-science.org A` and `AAAA` both return the VM, not
   `217.160.0.80` or `2001:8d8:...`.
2. Port 80 is reachable from outside: `curl -sI http://<VM IP>/` from your
   laptop, not from the VM itself.
3. `docker compose logs caddy` for the actual ACME error.

Let's Encrypt rate-limits **failed** validations to 5 per hostname per hour, so
if you have been fighting it for a while, fix the cause and then wait an hour
rather than retrying immediately.

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
