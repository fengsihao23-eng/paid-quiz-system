#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile public stop
python3 scripts/keep-awake.py stop
echo "服务已停止，数据库卷已保留。"
