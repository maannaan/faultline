#!/usr/bin/env bash
# Runs on the EC2 host (as root, via SSM Run Command) from /opt/faultline.
# Requires SITE_HOST in the environment on the first run.
set -euo pipefail
cd "$(dirname "$0")/.."

# First deploy only: create the server .env with random secrets. It never leaves the host.
if [ ! -f .env ]; then
  : "${SITE_HOST:?SITE_HOST is required on first deploy}"
  umask 077
  api_key=$(openssl rand -hex 24)
  cat > .env <<ENV
SITE_HOST=${SITE_HOST}
COMPOSE_PROFILES=local-graph
APP_ENV=development
FALKORDB_HOST=falkordb
FALKORDB_PORT=6379
FALKORDB_PASSWORD=$(openssl rand -hex 24)
AUTH_KEYS=${api_key}:tenant-synthetic,$(openssl rand -hex 24):tenant-other
FAULTLINE_API_KEY=${api_key}
OPENAI_API_KEY=
ENV
fi

docker compose -f docker-compose.prod.yml up -d --build --remove-orphans

# Seeding uses fixed idempotency keys, so repeating it is a no-op.
for _ in $(seq 1 20); do
  if docker compose -f docker-compose.prod.yml exec -T api python -m faultline.graph.seed; then
    break
  fi
  sleep 3
done

docker image prune -f >/dev/null
docker compose -f docker-compose.prod.yml ps
