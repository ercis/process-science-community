#!/usr/bin/env bash
#
# Read the join submissions.
#
#   ./submissions.sh count           how many so far
#   ./submissions.sh list            readable table, newest last
#   ./submissions.sh interests       tally of what people want to do
#   ./submissions.sh csv [file]      save the raw CSV (default join-YYYY-MM-DD.csv)
#   ./submissions.sh watch           live count, refreshed every 10s
#   ./submissions.sh remove ADDRESS  delete one person's row
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
if [ -z "${JOIN_EXPORT_TOKEN:-}" ]; then
	echo "No JOIN_EXPORT_TOKEN. Set it, or run this from the deploy/ directory that has .env." >&2
	exit 1
fi

api() {
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

watch)
	echo "Watching $SITE. Ctrl-C to stop."
	while true; do
		printf "\r%s  %s   " "$(date +%H:%M:%S)" "$(api count)"
		sleep 10
	done
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
