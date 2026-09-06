# Join collector

A small FastAPI service that receives the join form, stores it in SQLite, and
exports it as CSV. It exists so that the names, email addresses and employers
people type into the form stay on an ERCIS machine.

That is the main argument for running it rather than using a hosted form
service: the form collects personal data from people in the EU, and a US
provider such as Formspree would need a data processing agreement and a
transfer assessment before it could be used for this. Running the collector
next to the MATE API avoids that conversation entirely.

## What it does

| Route | Method | Auth | Purpose |
| --- | --- | --- | --- |
| `/join` | POST | none, CORS-restricted | Accepts a submission |
| `/healthz` | GET | none | Liveness probe |
| `/admin/submissions.csv` | GET | `Authorization: Bearer $JOIN_EXPORT_TOKEN` | Export everything |
| `/admin/count` | GET | same | How many so far |

Submissions are validated against the same closed sets of roles and interests
the form offers, so a malformed or tampered payload is rejected rather than
stored. There is a per-address rate limit and a honeypot field: a submission
with the honeypot filled gets the same `201` a human gets and is then discarded,
so a bot learns nothing. The OpenAPI schema and docs routes are switched off.

## Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `JOIN_DB_PATH` | `/data/join.sqlite3` | Put it on a mounted volume, not in the image |
| `JOIN_ALLOWED_ORIGINS` | the two `process-science.org` origins | Comma-separated. Nothing else may POST |
| `JOIN_EXPORT_TOKEN` | empty | **Required.** Export returns 503 until it is set. `openssl rand -hex 32` |
| `JOIN_RATE_LIMIT` | `20` | Requests per address per window. Rejected requests count too |
| `JOIN_RATE_WINDOW_S` | `3600` | |
| `JOIN_TRUST_PROXY` | `1` | Read the client address from `X-Forwarded-For`. Only correct behind a trusted proxy |

## Deploying on the existing VM

The cheapest route is to reuse the live `mate.uni-muenster.de` host rather than
asking the university to route a new hostname. No new DNS record, no new
certificate, no change at the edge proxy.

1. Copy this directory to the VM.
2. Put `JOIN_EXPORT_TOKEN=...` in a `.env` next to `docker-compose.yml`.
3. `docker compose up -d --build`
4. Add the block in `Caddyfile.snippet` inside the existing `:443` block of
   `infra/caddy/Caddyfile`, and make sure the collector shares a Docker network
   with Caddy so `join-collector:8080` resolves.
5. Reload Caddy.

The endpoint is then `https://mate.uni-muenster.de/community-join/join`.
Put exactly that in `FORM_ENDPOINT` at the top of `../assets/join.js`, and make
sure the page's origin is in `JOIN_ALLOWED_ORIGINS`.

Check it end to end before relying on it:

```bash
curl -i -X POST https://mate.uni-muenster.de/community-join/join \
  -H 'Content-Type: application/json' -H 'Origin: https://process-science.org' \
  -d '{"name":"Test","email":"test@example.org","organisation":"Test",
       "role":"Student","interest":"Be part of the community","consent":"yes"}'
```

A `201` with `access-control-allow-origin` in the response headers means the
page will work. Then delete the test row.

## Getting the submissions out

```bash
curl -H "Authorization: Bearer $JOIN_EXPORT_TOKEN" \
  https://mate.uni-muenster.de/community-join/admin/submissions.csv -o join.csv
```

## Running it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
JOIN_DB_PATH=./join.sqlite3 JOIN_EXPORT_TOKEN=dev \
  JOIN_ALLOWED_ORIGINS=http://localhost:8099 \
  .venv/bin/uvicorn app.main:app --port 8100
```

## Retention

Nothing here deletes anything. The consent line on the form promises people can
withdraw and be removed, so someone has to be able to act on that: deleting a
row is `DELETE FROM submissions WHERE lower(email) = lower('...')` against the
SQLite file. Agree who owns that before the form goes live.
