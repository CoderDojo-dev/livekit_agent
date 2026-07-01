#!/usr/bin/env bash
# Restore a logical backup (report #22).  Usage: restore.sh backups/telecom-YYYYMMDD-HHMMSS.dump
set -euo pipefail
: "${DATABASE_URL:?set DATABASE_URL}"
FILE="${1:?usage: restore.sh <dump-file>}"
PG_URL="${DATABASE_URL/+psycopg/}"
pg_restore --clean --if-exists --no-owner --dbname="$PG_URL" "$FILE"
echo "restored $FILE"