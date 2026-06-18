#!/usr/bin/env bash
#
# AllHaven — one-command production deploy. Run this ON YOUR VPS, from the repo
# root, after pointing your domain's DNS A record at the server.
#
#   git clone https://github.com/joshuasetiawann/AllHaven-Application.git
#   cd AllHaven-Application
#   DOMAIN=yourdomain.com ./deploy/deploy.sh
#
# It creates .env.prod (with strong random secrets) on first run, then builds and
# starts the stack (PostgreSQL + backend + frontend + Caddy auto-HTTPS). Re-run it
# to redeploy after `git pull`; an existing .env.prod is left untouched.
set -euo pipefail

cd "$(dirname "$0")/.."

: "${DOMAIN:?Set DOMAIN, e.g. DOMAIN=yourdomain.com ./deploy/deploy.sh}"

command -v docker >/dev/null || { echo "Docker is not installed. Install Docker + the compose plugin first."; exit 1; }

gen_secret() {
  if command -v python3 >/dev/null; then python3 -c "import secrets;print(secrets.token_urlsafe(48))";
  else openssl rand -base64 48 | tr -d '\n='; fi
}

if [ ! -f .env.prod ]; then
  echo "==> Creating .env.prod with generated secrets (DOMAIN=${DOMAIN})"
  cp .env.prod.example .env.prod
  sed -i.bak \
    -e "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(gen_secret)|" \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(gen_secret)|" \
    -e "s|^SETTINGS_ENCRYPTION_KEY=.*|SETTINGS_ENCRYPTION_KEY=$(gen_secret)|" \
    .env.prod
  rm -f .env.prod.bak
  echo "    .env.prod created. Review it if you want to set optional values (OLLAMA_BASE_URL, etc.)."
else
  echo "==> .env.prod already exists — using it as-is."
fi

echo "==> Building and starting the production stack ..."
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

cat <<EOF

==> Done. Caddy is provisioning HTTPS (give it ~30-60s on first run).
    Web app + API:   https://${DOMAIN}
    Mobile API base: https://${DOMAIN}/api/v1

Next, for the mobile APK download link:
  1. On GitHub: Settings -> Secrets and variables -> Actions -> Variables ->
     New variable  MOBILE_API_BASE_URL = https://${DOMAIN}/api/v1
  2. Actions -> "Build Android APK" -> Run workflow.
  3. The signed-for-debug app-debug.apk is published to the "mobile-latest"
     release: https://github.com/joshuasetiawann/AllHaven-Application/releases
EOF
