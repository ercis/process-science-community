#!/usr/bin/env bash
#
# Read the join submissions.
#
#   ./submissions.sh count           how many so far
#   ./submissions.sh list            readable table, newest last
#   ./submissions.sh interests       tally of what people want to do
#   ./submissions.sh outreach        who to contact, grouped by what they asked for
#   ./submissions.sh people          JSON lines for anyone not yet on the page
#   ./submissions.sh csv [file]      save the raw CSV (default join-YYYY-MM-DD.csv)
#   ./submissions.sh watch           live count, refreshed every 10s
#   ./submissions.sh remove ADDRESS  delete one person's row
#   ./submissions.sh sql "SELECT ..."  run a read-only query against the database
#
# The token comes from JOIN_EXPORT_TOKEN in the environment, or from the .env
# next to this script. Override the host with SITE_URL=... for a local stack.

set -euo pipefail

SITE="${SITE_URL:-https://process-science.org}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "${JOIN_EXPORT_TOKEN:-}" ] && [ -f "$here/.env" ]; then
	# shellcheck disable=SC1091
	set -a; . "$here/.env"; set +a
fi

# Only the commands that go over HTTP need the token. "sql" and "remove" talk
# to the container directly, so they must still work without one.
api() {
	if [ -z "${JOIN_EXPORT_TOKEN:-}" ]; then
		echo "No JOIN_EXPORT_TOKEN. Set it, or run this from the deploy/ directory that has .env." >&2
		exit 1
	fi
	curl -fsS -H "Authorization: Bearer $JOIN_EXPORT_TOKEN" "$SITE/api/admin/$1" || {
		echo "Request failed. Wrong token, or the site is not reachable at $SITE." >&2
		exit 1
	}
}

fetch_csv() { api "submissions.csv"; }

case "${1:-list}" in
count)
	api count
	echo
	;;

csv)
	out="${2:-join-$(date +%F).csv}"
	fetch_csv > "$out"
	echo "saved $out ($(($(wc -l < "$out") - 1)) submissions)"
	;;

list)
	fetch_csv | python3 -c '
import csv, sys, textwrap
rows = list(csv.DictReader(sys.stdin))
if not rows:
    print("No submissions yet."); sys.exit()
for i, r in enumerate(rows, 1):
    print("\033[1m%d. %s\033[0m  <%s>" % (i, r["name"], r["email"]))
    print("   %s  ·  %s  ·  %s" % (r["organisation"], r["role"], r["received_at"][:16].replace("T", " ")))
    print("   wants: %s" % r["interest"])
    if r["about"].strip():
        print(textwrap.fill(r["about"].strip(), 76,
              initial_indent="   note:  ", subsequent_indent="          "))
    print()
print("%d submission%s." % (len(rows), "" if len(rows) == 1 else "s"))
'
	;;

interests)
	fetch_csv | python3 -c '
import csv, sys
from collections import Counter
rows = list(csv.DictReader(sys.stdin))
c = Counter(i.strip() for r in rows for i in r["interest"].split(",") if i.strip())
roles = Counter(r["role"] for r in rows)
if not rows:
    print("No submissions yet."); sys.exit()
w = max(len(k) for k in c) if c else 0
print("What people want to do (%d people, more than one answer each):" % len(rows))
for k, n in c.most_common():
    print("  %-*s %3d  %s" % (w, k, n, "#" * n))
print("\nRoles:")
for k, n in roles.most_common():
    print("  %-28s %3d" % (k, n))
'
	;;

outreach)
	fetch_csv | python3 -c '
import csv, sys, textwrap

rows = list(csv.DictReader(sys.stdin))
if not rows:
    print("No submissions yet."); sys.exit()

GROUPS = [
    ("MATE, the research platform", [
        ("wants to USE it: bring an event log, run the modules", "Use the research platform"),
        ("wants to CONTRIBUTE: publish a method as a module",   "Contribute to the research platform"),
    ]),
    ("The teaching platform", [
        ("wants to USE it: bring a course",                      "Use the teaching platform"),
        ("wants to CONTRIBUTE: build material, shape the format", "Contribute to the teaching platform"),
    ]),
    ("Process Science in Practice", [
        ("wants to help shape it", "Help shape Process Science in Practice"),
    ]),
]

def wants(r, key):
    return key in [i.strip() for i in r["interest"].split(",")]

def show(r):
    print("     %s <%s>" % (r["name"], r["email"]))
    print("       %s  ·  %s  ·  joined %s" % (r["organisation"], r["role"], r["received_at"][:10]))
    if r["about"].strip():
        print(textwrap.fill(r["about"].strip(), 72,
              initial_indent="       \"", subsequent_indent="        ") + "\"")

claimed = set()
for title, buckets in GROUPS:
    hits = [(lbl, [r for r in rows if wants(r, key)]) for lbl, key in buckets]
    if not any(rs for _, rs in hits):
        continue
    print("\033[1m%s\033[0m" % title)
    for lbl, rs in hits:
        if not rs:
            continue
        print("   %s  (%d)" % (lbl, len(rs)))
        for r in rs:
            show(r); claimed.add(r["email"].lower())
        print()
    print()

rest = [r for r in rows if r["email"].lower() not in claimed]
if rest:
    print("\033[1mCommunity only, no platform asked for\033[0m  (%d)" % len(rest))
    print("   Still worth a welcome, and they go on the people list.")
    for r in rest:
        show(r)
    print()

print("%d people in total." % len(rows))
'
	;;

people)
	# Anyone who joined but is not yet in the people block of site/index.html.
	fetch_csv | python3 -c '
import csv, json, re, sys, unicodedata
from pathlib import Path

PARTICLES = {"van","von","vom","de","del","der","dos","da","di","la","le","ter","ten"}

def fold(t):
    t = t.replace("ß","ss")
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()

def initials(name):
    toks = name.split()
    if not toks:
        return ""
    if len(toks) == 1:
        return toks[0][0].upper()
    surname = toks[-1]
    # "del-Rio-Ortega" and friends: drop a leading particle before the hyphen
    head = surname.split("-")[0]
    if fold(head) in PARTICLES and "-" in surname:
        surname = surname.split("-", 1)[1]
    return (toks[0][0] + surname[0]).upper()

# The page is the source of truth for who is already listed. Its path is
# passed in by the shell, so this works from any working directory.
idx = Path(sys.argv[1]) if len(sys.argv) > 1 else None
existing = set()
if idx and idx.exists():
    m = re.search(r"id=\"people-data\">\s*\[(.*?)\]\s*</script>", idx.read_text(encoding="utf-8"), re.S)
    if m:
        for person in json.loads("[" + m.group(1) + "]"):
            existing.add(fold(person["name"]))
else:
    print("Warning: could not read %s, so nobody is treated as already listed.\n" % idx, file=sys.stderr)

rows = list(csv.DictReader(sys.stdin))
new = []
seen = set()
for r in rows:
    key = fold(r["name"])
    if key in existing or key in seen:
        continue
    seen.add(key)
    new.append(r)

if not rows:
    print("No submissions yet."); sys.exit()
if not new:
    print("Nothing to add: all %d people who joined are already on the page." % len(rows)); sys.exit()

print("%d of %d are not on the page yet.\n" % (len(new), len(rows)))
print("Paste these into the people-data block in site/index.html, then re-sort")
print("the block by surname and push. Check the initials for any name with a")
print("particle (\"van der\", \"vom\"): the rule here takes the last word.\n")
for r in new:
    print(json.dumps({"name": r["name"].strip(),
                      "affiliation": r["organisation"].strip(),
                      "initials": initials(r["name"].strip())},
                     ensure_ascii=False, separators=(",", ":")) + ",")
print("""
\033[1mBefore you publish these names\033[0m
The consent line on the form covers storing their details and replying by
email. It does not say their name will be listed publicly on the page. Ask
them first, or amend the form wording before collecting more.""")
' "$here/../site/index.html"
	;;

watch)
	echo "Watching $SITE. Ctrl-C to stop."
	while true; do
		printf "\r%s  %s   " "$(date +%H:%M:%S)" "$(api count)"
		sleep 10
	done
	;;

sql)
	# Ad-hoc questions. Runs on the VM against the database directly, so it
	# needs no token, only access to the container. Reads only: anything that
	# is not a SELECT is refused, because this is not the place to edit rows.
	query="${2:-}"
	[ -z "$query" ] && { echo 'usage: '"$0"' sql "SELECT name, email FROM submissions WHERE role LIKE '"'"'%Prof%'"'"'"' >&2; exit 1; }
	cid="$(docker ps -q --filter name=join-collector | head -1)"
	if [ -z "$cid" ]; then
		echo "The join-collector container is not running here. Run this on the VM." >&2
		exit 1
	fi
	docker exec -i "$cid" python - "$query" <<'PY'
import sqlite3, sys
q = sys.argv[1].strip()
if not q.lower().startswith("select"):
    sys.exit("Only SELECT is allowed here. To delete a row use: submissions.sh remove ADDRESS")
con = sqlite3.connect("file:/data/join.sqlite3?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute(q).fetchall()
if not rows:
    print("No rows."); raise SystemExit
cols = rows[0].keys()
widths = [max(len(c), max(len(str(r[c])) for r in rows)) for c in cols]
print("  ".join(c.ljust(w) for c, w in zip(cols, widths)))
print("  ".join("-" * w for w in widths))
for r in rows:
    print("  ".join(str(r[c]).ljust(w) for c, w in zip(cols, widths)))
print("\n%d row(s)." % len(rows))
PY
	;;

remove)
	addr="${2:-}"
	[ -z "$addr" ] && { echo "usage: $0 remove someone@example.org" >&2; exit 1; }
	# Address the container directly rather than through docker compose, which
	# would need the .env interpolated just to run one statement. The address is
	# passed as an argument, never spliced into the Python source.
	cid="$(docker ps -q --filter name=join-collector | head -1)"
	if [ -z "$cid" ]; then
		echo "The join-collector container is not running here. Run this on the VM." >&2
		exit 1
	fi
	docker exec -i "$cid" python - "$addr" <<'PY'
import sqlite3, sys
addr = sys.argv[1]
con = sqlite3.connect("/data/join.sqlite3")
n = con.execute("DELETE FROM submissions WHERE lower(email) = lower(?)", (addr,)).rowcount
con.commit()
print("removed %d row(s) for %s" % (n, addr))
PY
	;;

*)
	sed -n '3,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
	exit 1
	;;
esac
