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
sudo -n docker compose up -d --build --remove-orphans
git rev-parse origin/main > data/.deployed_sha
