#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/setup-local.py
docker compose --profile public up --build -d
python3 scripts/tunnel-url.py
if [ "$(uname)" = "Darwin" ]; then
  if [ ! -f .runtime/caffeinate.pid ] || ! kill -0 "$(cat .runtime/caffeinate.pid)" 2>/dev/null; then
    nohup caffeinate -i > .runtime/caffeinate.log 2>&1 &
    echo "$!" > .runtime/caffeinate.pid
  fi
fi
echo "本机：http://localhost:18990  管理：http://localhost:18991/admin/"
