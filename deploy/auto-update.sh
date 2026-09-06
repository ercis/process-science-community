#!/usr/bin/env bash
#
# Pull the repository and apply whatever changed. Run by a systemd timer, so
# pushing to main updates the live site on its own, the way GitHub Pages does.
#
# site/ is a read-only bind mount into Caddy, so for a page or content change a
# pull IS the deployment: nothing to build, nothing to restart. Only a change
# under service/ or deploy/ needs the stack brought back up.

set -euo pipefail

REPO="${REPO_DIR:-/root/process-science-community}"
BRANCH="${BRANCH:-main}"

cd "$REPO"

git fetch --quiet origin "$BRANCH"
local_rev=$(git rev-parse HEAD)
remote_rev=$(git rev-parse "origin/$BRANCH")

if [ "$local_rev" = "$remote_rev" ]; then
	exit 0
fi

changed=$(git diff --name-only "$local_rev" "$remote_rev")
echo "updating ${local_rev:0:8} -> ${remote_rev:0:8}"
echo "$changed" | sed 's/^/  /'

# This checkout is a deploy target, not a workspace: the remote always wins.
# deploy/.env is gitignored, so it survives.
git reset --hard --quiet "origin/$BRANCH"

if printf '%s\n' "$changed" | grep -qE '^(service/|deploy/)'; then
	echo "service or deploy changed: rebuilding the stack"
	cd "$REPO/deploy"
	docker compose up -d --build
else
	echo "site only: already live through the bind mount"
fi

echo "now at $(git rev-parse --short HEAD)"
