#!/bin/sh
set -eu
cd "$(dirname "$0")"
docker compose exec -T backend python manage.py check
docker compose exec -T backend python manage.py makemigrations --check --dry-run
docker compose exec -T backend python manage.py test --noinput
cd frontend
npm run lint
npm test
npm run build
