#!/usr/bin/env bash
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups/$DATE"
mkdir -p "$BACKUP_DIR"

echo "Starting backup: $DATE"

# PostgreSQL
echo "  Backing up PostgreSQL..."
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-osint}" "${POSTGRES_DB:-osint}" \
  | gzip > "$BACKUP_DIR/postgres.sql.gz"

# Redis
echo "  Backing up Redis..."
docker compose exec -T redis redis-cli BGSAVE > /dev/null 2>&1
sleep 2
docker compose cp redis:/data/dump.rdb "$BACKUP_DIR/redis.rdb" 2>/dev/null || true

echo "Backup completed: $BACKUP_DIR"
ls -lh "$BACKUP_DIR/"

# Cleanup old backups (keep 30 days)
find ./backups -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true
