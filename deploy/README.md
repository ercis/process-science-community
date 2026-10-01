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

`site/` is a read-only bind mount, so for a content change a pull **is** the
deployment. Nothing to build, nothing to restart:

```bash
git pull
```

A change under `service/` or `deploy/` does need the stack brought back up:

```bash
docker compose up -d --build
```

### Automatic updates from git

To get GitHub Pages behaviour, where pushing to `main` updates the live site on
its own, install the timer. It polls once a minute, pulls when there is
something to pull, and rebuilds only when `service/` or `deploy/` changed.

```bash
sudo cp deploy/process-science-update.{service,timer} /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now process-science-update.timer
```

Check it:

```bash
systemctl list-timers process-science-update.timer
```

Watch what it does:

```bash
journalctl -u process-science-update.service -f
```

The units assume the checkout is at `/root/process-science-community`. If it is
somewhere else, edit `WorkingDirectory` and `ExecStart` in the `.service` file,
or set `REPO_DIR` in it.

**Polling rather than a webhook is deliberate.** A webhook would need an
inbound endpoint, a shared secret and HMAC verification, all to save under a
minute on a site whose deployment is a `git pull`. The timer needs no secret
and no inbound access, and it recovers on its own after a reboot or a network
blip, which a missed webhook delivery does not.

One consequence worth knowing: **the checkout on the VM is a deploy target, not
a workspace.** The updater runs `git reset --hard origin/main`, so anything
edited directly on the server is discarded on the next tick. Make changes in
the repository and push them. `deploy/.env` is gitignored and survives.

## Reading the submissions

`submissions.sh` wraps the export. Run it from `deploy/`, where it picks the
token out of `.env` by itself:

```bash
./submissions.sh list
```

| Command | What it does |
| --- | --- |
| `./submissions.sh count` | how many so far |
| `./submissions.sh list` | every submission, readable, newest last |
| `./submissions.sh interests` | tally of what people want to do, and roles |
| `./submissions.sh outreach` | who to contact, grouped by what they asked for |
| `./submissions.sh people` | JSON lines for anyone not yet on the people list |
| `./submissions.sh csv [file]` | save the raw CSV for a spreadsheet |
| `./submissions.sh watch` | live count, refreshed every 10s |
| `./submissions.sh sql "SELECT ..."` | ad-hoc read-only query |
| `./submissions.sh remove ADDRESS` | delete one person's row |

`outreach` is the one to work from after an event. It splits people by what
they actually asked for, so the research platform list and the teaching
platform list are separate, and **use** is separate from **contribute**, which
is the whole reason that question is on the form. It prints each person's free
text too, because that is what tells you what to say to them.

`people` compares the submissions against the people block in
`site/index.html` and prints ready-to-paste JSON lines for anyone missing,
with the initials worked out. Paste them in, re-sort the block by surname, and
push. Check the initials by hand for any name with a particle: the rule takes
the last word, which is right for "van der Berg" and wrong for a few others.

`sql` and `remove` talk to the container directly, so they only work on the VM
and need no token. `sql` refuses anything that is not a `SELECT`.

### Consent, before you publish anyone's name

The consent line on the form covers **storing their details and replying by
email**. It does not say their name and affiliation will be listed publicly on
the landing page. The people list is a public page on a public domain, so
before adding anyone from the form, either ask them, or change the form wording
and only auto-add people who agreed to the new wording. `people` prints this
reminder every time for a reason.

It works from a laptop too, given the token:

```bash
JOIN_EXPORT_TOKEN=... ./submissions.sh list
```

Under it is one authenticated request:

```bash
curl -H "Authorization: Bearer $JOIN_EXPORT_TOKEN" https://process-science.org/api/admin/submissions.csv
```

The export routes are reachable from the internet and protected by that bearer
token alone, so treat it like a password: it is the only thing between the
internet and everybody's contact details. Rotating it is an edit to `.env` and
`docker compose up -d join-collector`.

`remove` exists because the consent line on the form promises people can
withdraw and be removed. Somebody has to own acting on that.

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
