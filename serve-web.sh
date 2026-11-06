#!/usr/bin/env bash
# Build the static site and serve it locally, the same files GitHub Pages gets.
#
#   ./serve-web.sh              # reuse output/recommendations/, else compute levels 1-100 (about 3 minutes)
#   ./serve-web.sh 1,20,40      # recompute these levels first (ranges and lists, as `recommend --levels`)
#   ./serve-web.sh stop         # stop a server left running
#
# Opens the site in the browser (NO_OPEN=1: only the server); PORT changes the port (4321). Ctrl+C stops it.
set -euo pipefail

cd "$(dirname "$0")"
if [[ "${1:-}" == "stop" ]]; then
  cd web && exec npx astro preview stop
fi
PORT="${PORT:-4321}"
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

cd web
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build
URL="http://localhost:$PORT/farm-production-recipe-dependency-graph/"
# astro preview may detach on its own, so the script starts it in the background and stops it on exit
npx astro preview --background --port "$PORT"
trap 'npx astro preview stop >/dev/null' EXIT
echo "Site: $URL (Ctrl+C stops)"
if [[ -z "${NO_OPEN:-}" ]] && command -v xdg-open >/dev/null; then
  xdg-open "$URL" >/dev/null 2>&1 || true
fi
npx astro preview logs --follow
