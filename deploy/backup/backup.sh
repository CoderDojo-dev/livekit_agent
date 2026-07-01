#!/usr/bin/env bash
# Nightly logical backup of the platform DB (report #22). Cron: 0 2 * * *
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$OUT_DIR/telecom-$STAMP.dump"
# pg_dump understands the libpq URL (strip the +psycopg driver suffix)
PG_URL="${DATABASE_URL/+psycopg/}"
pg_dump --format=custom --no-owner --dbname="$PG_URL" --file="$FILE"
echo "wrote $FILE"
# retention: keep the newest 14
ls -1t "$OUT_DIR"/telecom-*.dump | tail -n +15 | xargs -r rm -f
echo "backup complete"