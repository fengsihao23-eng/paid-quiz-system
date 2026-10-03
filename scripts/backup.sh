#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
mkdir -p backups
chmod 700 backups
backup_path="backups/paid-quiz-$(date +%Y%m%d-%H%M%S).dump"
umask 077
docker compose exec -T db pg_dump -U paid_quiz -d paid_quiz -Fc > "$backup_path"
echo "数据库已备份到 ${backup_path}；恢复时还须保留 .env 中的原密钥。"
