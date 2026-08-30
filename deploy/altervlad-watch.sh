#!/bin/bash
# Poll origin/main. Skip quietly when already deployed or .env is still a placeholder.
set -euo pipefail
cd /srv/containers/altervlad
git fetch --prune origin
remote=$(git rev-parse origin/main)
deployed=""
if [[ -f data/.deployed_sha ]]; then
  deployed=$(tr -d '[:space:]' < data/.deployed_sha)
fi
if [[ "$deployed" == "$remote" ]]; then
  exit 0
fi
if [[ ! -f .env ]] || grep -q 'your_discord_bot_token_here' .env; then
  exit 0
fi
exec /usr/local/bin/altervlad-deploy.sh
