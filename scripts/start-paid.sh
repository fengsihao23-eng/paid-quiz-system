#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 scripts/setup-local.py --paid
if [ -f .runtime/paid-preview.override.yml ] && [ "$(docker inspect -f '{{.State.Running}}' paid-quiz-paid-preview-frontend-1 2>/dev/null || true)" = "true" ]; then
  docker compose -p paid-quiz-paid-preview -f docker-compose.yml -f .runtime/paid-preview.override.yml stop
fi
paid_compose() {
  docker compose -p paid-quiz-paid --env-file .runtime/paid.env -f docker-compose.yml -f docker-compose.paid.yml --profile public "$@"
}
paid_compose up --build -d --wait --wait-timeout 120 db redis backend frontend
paid_compose exec -T backend python manage.py publish_content --reason '运营者启动完整娱乐测评收费版'
paid_compose up -d --no-deps tunnel
python3 scripts/tunnel-url.py --paid
python3 scripts/keep-awake.py start
echo "完整收费版本机：http://localhost:18992  管理：http://localhost:18993/admin/"
