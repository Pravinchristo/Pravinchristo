#!/bin/bash
# Installs (first run) and starts a local SearXNG instance on 127.0.0.1:8888.
# Safe to run repeatedly: it exits early if the server is already up.
set -u
PORT="${SEARXNG_PORT:-8888}"
HOME_DIR="${SEARXNG_HOME:-$HOME/.cache/searxng}"
SRC="$HOME_DIR/src"
VENV="$HOME_DIR/venv"
CONF="$HOME_DIR/settings.yml"
LOG="$HOME_DIR/searxng.log"

if curl -s -o /dev/null --noproxy '*' -m 2 "http://127.0.0.1:$PORT/healthz"; then
  echo "SearXNG already running on port $PORT"
  exit 0
fi

mkdir -p "$HOME_DIR"
if [ ! -d "$SRC/searx" ]; then
  git clone -q --depth 1 https://github.com/searxng/searxng "$SRC" || { echo "clone failed"; exit 1; }
fi
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" && "$VENV/bin/pip" install -q -r "$SRC/requirements.txt" || { echo "pip install failed"; exit 1; }
fi

if [ ! -f "$CONF" ]; then
  {
    echo "use_default_settings: true"
    echo "server:"
    echo "  secret_key: \"$(openssl rand -hex 32)\""
    echo "  limiter: false"
    echo "  bind_address: \"127.0.0.1\""
    echo "  port: $PORT"
    echo "search:"
    echo "  formats: [html, json]"
    echo "valkey:"
    echo "  url: false"
    echo "outgoing:"
    echo "  request_timeout: 6.0"
    # Route engine traffic through the cloud session's proxy when one is set.
    if [ -n "${HTTPS_PROXY:-}" ]; then
      [ -f /root/.ccr/ca-bundle.crt ] && echo "  verify: /root/.ccr/ca-bundle.crt"
      echo "  proxies:"
      echo "    all://:"
      echo "      - $HTTPS_PROXY"
    fi
  } > "$CONF"
fi

cd "$HOME_DIR" && SEARXNG_SETTINGS_PATH="$CONF" PYTHONPATH="$SRC" \
  nohup "$VENV/bin/python" -m searx.webapp > "$LOG" 2>&1 &

for _ in $(seq 1 60); do
  curl -s -o /dev/null --noproxy '*' -m 2 "http://127.0.0.1:$PORT/healthz" && { echo "SearXNG started on port $PORT"; exit 0; }
  sleep 1
done
echo "SearXNG did not start; see $LOG"
exit 1
