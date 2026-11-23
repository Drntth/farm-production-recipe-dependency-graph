#!/usr/bin/env bash
# Build the static site and serve it locally, the same files GitHub Pages gets.
#
#   ./serve-web.sh              # reuse output/recommendations/, else compute levels 1-100 (about 3 minutes)
#   ./serve-web.sh 1,20,40      # recompute these levels first (ranges and lists, as `recommend --levels`)
#   ./serve-web.sh --host       # only on the LAN / Wi-Fi address (a phone on the same Wi-Fi), not on localhost or a VPN
#   ./serve-web.sh --host 1,20  # options and levels combine, in any order
#   ./serve-web.sh stop         # stop a server left running
#
# Opens the site in the browser (NO_OPEN=1: only the server); PORT changes the port (4321). Ctrl+C stops it.
set -euo pipefail

cd "$(dirname "$0")"
# --host may stand anywhere; the rest is `stop` or a level list
LAN=
ARGS=()
for arg in "$@"; do
  if [[ "$arg" == "--host" ]]; then
    LAN=1
  else
    ARGS+=("$arg")
  fi
done
set -- "${ARGS[@]}"
if [[ "${1:-}" == "stop" ]]; then
  cd web && exec npx astro preview stop
fi
PORT="${PORT:-4321}"
HOST_ARGS=()
HOST=localhost
if [[ -n "$LAN" ]]; then
  # the first LAN / Wi-Fi address: not loopback, Docker bridges, VPN tunnels or virtual links;
  # the server listens on it alone, so a VPN address of this machine does not serve the site
  HOST="$(ip -4 -o addr show scope global 2>/dev/null |
    awk '$2 !~ /^(docker|br-|veth|virbr|tun|tap|wg|tailscale|zt)/ {sub(/\/.*/, "", $4); print $4; exit}')"
  if [[ -z "$HOST" ]]; then
    echo "No LAN / Wi-Fi address found (is the Wi-Fi connected?)." >&2
    exit 1
  fi
  HOST_ARGS=(--host "$HOST")
fi
REC_DIR=output/recommendations

if [[ -x venv/bin/python ]]; then
  PY=venv/bin/python
else
  PY=python3
fi

if [[ $# -gt 0 ]]; then
  "$PY" -m src recommend --levels "$1" --output-dir "$REC_DIR"
elif [[ ! -f "$REC_DIR/index.json" ]]; then
  echo "No $REC_DIR/index.json: computing levels 1-100 (about 3 minutes)."
  "$PY" -m src recommend --output-dir "$REC_DIR"
fi
# the browser planner of "My farms": core.zip, data bundle, level defaults → web/public/py/
"$PY" -m src web-files

cd web
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build
URL="http://$HOST:$PORT/farm-production-recipe-dependency-graph/"
# astro preview may detach on its own, so the script starts it in the background and stops it on exit
npx astro preview --background --port "$PORT" "${HOST_ARGS[@]}"
trap 'npx astro preview stop >/dev/null' EXIT
echo "Site: $URL (Ctrl+C stops)"
if [[ -n "$LAN" ]]; then
  echo "Only on the local network (phone on the same Wi-Fi); not on localhost or a VPN address."
fi
if [[ -z "${NO_OPEN:-}" ]] && command -v xdg-open >/dev/null; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi
npx astro preview logs --follow
