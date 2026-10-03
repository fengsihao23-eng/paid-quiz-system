#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/setup-local.py
docker compose --profile public up --build -d
python3 scripts/tunnel-url.py
python3 scripts/keep-awake.py start
echo "本机：http://localhost:18990  管理：http://localhost:18991/admin/"
