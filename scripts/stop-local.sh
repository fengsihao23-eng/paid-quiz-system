#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile public stop
if [ "$(docker inspect -f '{{.State.Running}}' paid-quiz-paid-frontend-1 2>/dev/null || true)" != "true" ]; then
  python3 scripts/keep-awake.py stop
fi
echo "服务已停止，数据库卷已保留。"
