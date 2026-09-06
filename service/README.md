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

## Deploying

It is not deployed on its own. `deploy/docker-compose.yml` builds this
directory and runs it behind Caddy on the same VM as the landing page, and
`deploy/Caddyfile` proxies `/api/*` here after stripping the prefix, so the
service itself only ever sees `/join`. See
[`../deploy/README.md`](../deploy/README.md).

Because the page and the collector share an origin, the browser sends no
cross-origin request and `JOIN_ALLOWED_ORIGINS` stays empty. Anything that does
arrive cross-origin is refused.

## Running it locally

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
JOIN_DB_PATH=./join.sqlite3 JOIN_EXPORT_TOKEN=dev \
  .venv/bin/uvicorn app.main:app --port 8100
```

To exercise the real arrangement instead, including Caddy, the strict CSP and
the same-origin `/api` path, run the stack from `deploy/`.

## Retention

Nothing here deletes anything. The consent line on the form promises people can
withdraw and be removed, so someone has to be able to act on that. There is a
one-liner for it in [`../deploy/README.md`](../deploy/README.md). Agree who owns
that before the form goes live.
