#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

if ! command -v docker >/dev/null 2>&1; then
  $SUDO apt-get update
  $SUDO apt-get install -y docker.io curl openssl
  $SUDO systemctl enable --now docker
fi

if ! docker compose version >/dev/null 2>&1; then
  $SUDO apt-get update
  $SUDO apt-get install -y docker-compose-v2 || $SUDO apt-get install -y docker-compose-plugin
fi

if [[ ! -f .env ]]; then
  ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '\n/+=' | cut -c1-22)@A9"
  SESSION_SECRET="$(openssl rand -hex 48)"
  cat > .env <<EOF
APP_PORT=${APP_PORT:-80}
JM_ADMIN_USER=admin
JM_ADMIN_PASSWORD=${ADMIN_PASSWORD}
JM_SESSION_SECRET=${SESSION_SECRET}
JM_OPDS_USER=admin
JM_OPDS_PASSWORD=${ADMIN_PASSWORD}
JM_LIBRARY_DIR=/data/pdf
EOF
  chmod 600 .env
fi

set -a
source .env
set +a

$SUDO docker compose up -d --build

if command -v ufw >/dev/null 2>&1 && $SUDO ufw status | grep -q "Status: active"; then
  $SUDO ufw allow "${APP_PORT}/tcp"
fi

HOST_IP="$(curl -4fsS --max-time 5 https://api.ipify.org || hostname -I | awk '{print $1}')"
echo
echo "JMComic Cloud deployed"
echo "Web:  http://${HOST_IP}:${APP_PORT}/"
echo "OPDS: http://${HOST_IP}:${APP_PORT}/opds"
echo "User: ${JM_ADMIN_USER}"
echo "Password: ${JM_ADMIN_PASSWORD}"
