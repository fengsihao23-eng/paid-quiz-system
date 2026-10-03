#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose -p paid-quiz-paid --env-file .runtime/paid.env -f docker-compose.yml -f docker-compose.paid.yml --profile public stop
if [ "$(docker inspect -f '{{.State.Running}}' paid-quiz-customer-test-frontend-1 2>/dev/null || true)" != "true" ]; then
  python3 scripts/keep-awake.py stop
fi
echo "收费版已停止，数据库卷已保留。"
