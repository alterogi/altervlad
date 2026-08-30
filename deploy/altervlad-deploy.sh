#!/bin/bash
# Runs on memv3 via a forced SSH command. Do not put secrets here.
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
sudo -n docker compose up -d --build --remove-orphans
