#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
umask 077
case "${1:-}" in
  --paid)
    backup_path="backups/paid-full-$(date +%Y%m%d-%H%M%S).dump"
    docker compose -p paid-quiz-paid --env-file .runtime/paid.env -f docker-compose.yml -f docker-compose.paid.yml exec -T db pg_dump -U paid_quiz -d paid_quiz -Fc > "$backup_path"
    echo "收费版已备份到 ${backup_path}；恢复时还须保留 .runtime/paid.env 中的原密钥。"
    ;;
  '')
    backup_path="backups/paid-quiz-$(date +%Y%m%d-%H%M%S).dump"
    docker compose exec -T db pg_dump -U paid_quiz -d paid_quiz -Fc > "$backup_path"
    echo "测试版已备份到 ${backup_path}；恢复时还须保留 .env 中的原密钥。"
    ;;
  *) echo "用法：./scripts/backup.sh [--paid]" >&2; exit 1 ;;
esac
