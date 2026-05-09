#!/usr/bin/env bash
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
ENV_FILE="${WECHAT_OBSIDIAN_ENV_FILE:-}"
PYTHON_BIN="$SKILL_ROOT/.venv/bin/python"
ROUTER="$SKILL_ROOT/scripts/url_router.py"

if [ ! -x "$PYTHON_BIN" ]; then
  echo '{"status":"failed","source":"runner","error":"Python virtual environment not found or not executable."}'
  exit 1
fi

if [ ! -f "$ROUTER" ]; then
  echo '{"status":"failed","source":"runner","error":"url_router.py not found."}'
  exit 1
fi

if [ -z "$ENV_FILE" ]; then
  if [ -f "$CONFIG_HOME/wechat-obsidian-inbox/env" ]; then
    ENV_FILE="$CONFIG_HOME/wechat-obsidian-inbox/env"
  elif [ -f "$CONFIG_HOME/openclaw-wechat-obsidian/env" ]; then
    ENV_FILE="$CONFIG_HOME/openclaw-wechat-obsidian/env"
  fi
fi

if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

exec "$PYTHON_BIN" "$ROUTER" "$@"
