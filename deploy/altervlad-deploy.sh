#!/bin/bash
# Frozen copy lives at /usr/local/bin/altervlad-deploy.sh (root-owned).
# Do not put secrets here.
set -euo pipefail
cd /srv/containers/altervlad
git fetch --prune origin
git reset --hard origin/main
mkdir -p data
if [[ ! -f .env ]]; then
  echo "missing /srv/containers/altervlad/.env — not starting" >&2
  exit 1
fi
if grep -q 'your_discord_bot_token_here' .env; then
  echo ".env still has placeholder DISCORD_TOKEN — not starting" >&2
  exit 1
fi
sudo -n docker run --rm \
  -v /srv/containers/altervlad:/src:ro \
  -w /src python:3.12-slim \
  bash -c 'pip install -q -r requirements.txt pytest && pytest -q'
COMMIT_SHA=$(git rev-parse origin/main)
COMMIT_SHORT_SHA=$(git rev-parse --short origin/main)
COMMIT_MSG=$(git log -1 --pretty=%s origin/main)
COMMIT_AUTHOR=$(git log -1 --pretty=%an origin/main)
COMMIT_TIMESTAMP=$(git log -1 --pretty=%cI origin/main)

python3 -c "
import json, sys
info = {
    'sha': sys.argv[1],
    'short_sha': sys.argv[2],
    'message': sys.argv[3],
    'author': sys.argv[4],
    'timestamp': sys.argv[5]
}
with open('data/deployed_info.json', 'w', encoding='utf-8') as f:
    json.dump(info, f, indent=2)
" "$COMMIT_SHA" "$COMMIT_SHORT_SHA" "$COMMIT_MSG" "$COMMIT_AUTHOR" "$COMMIT_TIMESTAMP"

echo "$COMMIT_SHA" > data/.deployed_sha

sudo -n docker compose up -d --build --remove-orphans

