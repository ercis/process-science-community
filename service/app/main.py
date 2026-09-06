"""
Join collector for the Process Science Community.

A deliberately small FastAPI service: it accepts the join form's JSON, validates
it, writes it to SQLite, and lets an authorised caller export the list as CSV.
No third-party processor is involved, which is the point: the form collects
names, email addresses and employers of people in the EU, and keeping that on
an ERCIS machine avoids putting a data processing agreement with a US provider
on the critical path.

Run it next to the MATE API on the existing VM and let the existing Caddy fan
one path to it. See ../README.md for the deployment snippets.
"""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import time
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator

# --- configuration, all from the environment ---------------------------------

DB_PATH = Path(os.environ.get("JOIN_DB_PATH", "/data/join.sqlite3"))
# Comma-separated list of origins allowed to post. The landing page's origin.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "JOIN_ALLOWED_ORIGINS",
        "https://process-science.org,https://www.process-science.org",
    ).split(",") if o.strip()
]
# Bearer token for the CSV export. No default: exporting is off until it is set.
EXPORT_TOKEN = os.environ.get("JOIN_EXPORT_TOKEN", "")
# Requests per window per client address, to blunt casual abuse.
RATE_LIMIT = int(os.environ.get("JOIN_RATE_LIMIT", "20"))
RATE_WINDOW_S = int(os.environ.get("JOIN_RATE_WINDOW_S", "3600"))
# Set to 1 only when a trusted reverse proxy sets X-Forwarded-For.
TRUST_PROXY = os.environ.get("JOIN_TRUST_PROXY", "1") == "1"

ROLES = {
    "Professor or Lecturer", "PhD student or Postdoc",
    "Researcher outside academia", "Student",
    "Practitioner or Industry", "Other",
}
INTERESTS = {
    "Be part of the community", "Use the research platform",
    "Contribute to the research platform", "Use the teaching platform",
    "Contribute to the teaching platform", "Help shape Process Science in Practice",
}

# --- storage -----------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at   TEXT NOT NULL,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    organisation  TEXT NOT NULL,
    role          TEXT NOT NULL,
    interest      TEXT NOT NULL,
    about         TEXT NOT NULL DEFAULT '',
    consent       TEXT NOT NULL,
    source        TEXT NOT NULL DEFAULT '',
    user_agent    TEXT NOT NULL DEFAULT ''
);
-- One row per person. A second submission with the same address updates nothing
-- automatically, but the index makes duplicates trivial to find before mailing.
CREATE INDEX IF NOT EXISTS idx_submissions_email ON submissions(lower(email));
"""


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode=WAL")
        yield con
        con.commit()
    finally:
        con.close()


with db() as _con:
    _con.executescript(SCHEMA)

# --- rate limiting -----------------------------------------------------------

_hits: dict[str, deque[float]] = {}


def client_ip(request: Request) -> str:
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    ip = client_ip(request)
    now = time.monotonic()
    seen = _hits.setdefault(ip, deque())
    while seen and now - seen[0] > RATE_WINDOW_S:
        seen.popleft()
    if len(seen) >= RATE_LIMIT:
        raise HTTPException(429, "Too many submissions from this address. Please email us instead.")
    seen.append(now)
    if len(_hits) > 10_000:            # keep the table from growing without bound
        for k in [k for k, v in _hits.items() if not v or now - v[-1] > RATE_WINDOW_S]:
            _hits.pop(k, None)

# --- request model -----------------------------------------------------------


class Submission(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    organisation: str = Field(min_length=1, max_length=300)
    role: str = Field(min_length=1, max_length=100)
    interest: str = Field(min_length=1, max_length=500)
    about: str = Field(default="", max_length=5000)
    consent: Literal["yes"]
    source: str = Field(default="", max_length=60)
    submitted_at: str = Field(default="", max_length=40)
    # Honeypot: a hidden field no human fills in. Bots fill everything.
    website: str = Field(default="", max_length=200)

    @field_validator("name", "organisation", "role", "about", "source")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("role")
    @classmethod
    def _known_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("unknown role")
        return v

    @field_validator("interest")
    @classmethod
    def _known_interests(cls, v: str) -> str:
        picked = [p.strip() for p in v.split(",") if p.strip()]
        if not picked:
            raise ValueError("choose at least one")
        unknown = set(picked) - INTERESTS
        if unknown:
            raise ValueError("unknown interest: %s" % ", ".join(sorted(unknown)))
        return ", ".join(picked)


app = FastAPI(title="Process Science Community join collector", version="1.0.0",
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    max_age=86400,
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/join", status_code=201, dependencies=[Depends(rate_limit)])
def join(payload: Submission, request: Request) -> dict[str, str]:
    # A filled honeypot is a bot. Answer 201 so it does not learn anything, and
    # drop the row on the floor.
    if payload.website:
        return {"status": "ok"}
    with db() as con:
        con.execute(
            """INSERT INTO submissions
               (received_at, name, email, organisation, role, interest, about,
                consent, source, user_agent)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),
             payload.name, str(payload.email), payload.organisation, payload.role,
             payload.interest, payload.about, payload.consent, payload.source,
             request.headers.get("user-agent", "")[:300]),
        )
    return {"status": "ok"}


def require_export_token(authorization: str = Header(default="")) -> None:
    if not EXPORT_TOKEN:
        raise HTTPException(503, "Export is not configured.")
    if authorization != f"Bearer {EXPORT_TOKEN}":
        raise HTTPException(401, "Not authorised.")


@app.get("/admin/submissions.csv", dependencies=[Depends(require_export_token)])
def export_csv() -> Response:
    with db() as con:
        rows = con.execute(
            "SELECT received_at, name, email, organisation, role, interest,"
            " about, consent, source FROM submissions ORDER BY id"
        ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["received_at", "name", "email", "organisation", "role",
                "interest", "about", "consent", "source"])
    w.writerows([tuple(r) for r in rows])
    return Response(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="join-submissions.csv"'},
    )


@app.get("/admin/count", dependencies=[Depends(require_export_token)])
def count() -> dict[str, int]:
    with db() as con:
        return {"submissions": con.execute("SELECT count(*) FROM submissions").fetchone()[0]}
