#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile public stop
if [ -f .runtime/caffeinate.pid ]; then
  kill "$(cat .runtime/caffeinate.pid)" 2>/dev/null || true
  rm .runtime/caffeinate.pid
fi
echo "服务已停止，数据库卷已保留。"
