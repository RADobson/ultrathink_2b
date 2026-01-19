#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: sudo $0 <username> <web_port>"
  echo "Example: sudo $0 alice 8081"
}

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "This script must be run as root."
  exit 1
fi

USERNAME="${1:-}"
WEB_PORT="${2:-}"

if [[ -z "$USERNAME" || -z "$WEB_PORT" ]]; then
  usage
  exit 1
fi

if ! id -u "$USERNAME" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$USERNAME"
fi

usermod -aG docker "$USERNAME" || true

USER_HOME="/home/$USERNAME"
VAULT_DIR="$USER_HOME/vault"
REPO_DEST="$USER_HOME/ultrathink"
REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$VAULT_DIR"
chown -R "$USERNAME":"$USERNAME" "$VAULT_DIR"

if [[ ! -d "$REPO_DEST" ]]; then
  mkdir -p "$REPO_DEST"
  rsync -a \
    --exclude '.git' \
    --exclude 'vault' \
    --exclude '.env' \
    --exclude '.env.*' \
    "$REPO_SRC/" "$REPO_DEST/"
  chown -R "$USERNAME":"$USERNAME" "$REPO_DEST"
fi

ENV_PATH="$REPO_DEST/.env"
if [[ -f "$ENV_PATH" ]]; then
  read -r -p "A .env already exists for $USERNAME. Overwrite? (y/N): " OVERWRITE
  if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
    echo "Keeping existing .env."
  fi
fi

if [[ ! -f "$ENV_PATH" || "${OVERWRITE:-}" =~ ^[Yy]$ ]]; then
  read -r -p "Telegram bot token: " TELEGRAM_BOT_TOKEN
  read -r -p "Telegram chat ID: " TELEGRAM_CHAT_ID
  read -r -p "Anthropic API key: " ANTHROPIC_API_KEY
  read -r -p "OpenAI API key: " OPENAI_API_KEY
  read -r -p "Timezone [Australia/Brisbane]: " TIMEZONE
  read -r -p "Confidence threshold [0.6]: " CONFIDENCE_THRESHOLD
  read -r -p "Web username [admin]: " WEB_USERNAME
  read -r -s -p "Web password: " WEB_PASSWORD
  echo ""

  TIMEZONE="${TIMEZONE:-Australia/Brisbane}"
  CONFIDENCE_THRESHOLD="${CONFIDENCE_THRESHOLD:-0.6}"
  WEB_USERNAME="${WEB_USERNAME:-admin}"
  PUID="$(id -u "$USERNAME")"
  PGID="$(id -g "$USERNAME")"

  cat > "$ENV_PATH" <<EOF
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
OPENAI_API_KEY=$OPENAI_API_KEY
TIMEZONE=$TIMEZONE
CONFIDENCE_THRESHOLD=$CONFIDENCE_THRESHOLD
PUID=$PUID
PGID=$PGID
WEB_USERNAME=$WEB_USERNAME
WEB_PASSWORD=$WEB_PASSWORD
WEB_SECRET=
EOF
  chown "$USERNAME":"$USERNAME" "$ENV_PATH"
fi

sed -i -E "s/\"[0-9]{2,5}:8000\"/\"${WEB_PORT}:8000\"/" "$REPO_DEST/docker-compose.yml"

docker compose --env-file "$ENV_PATH" -p "$USERNAME" -f "$REPO_DEST/docker-compose.yml" up -d --build

echo "Onboarded $USERNAME."
echo "Vault: $VAULT_DIR"
echo "Web UI: http://<server-ip>:${WEB_PORT}"
