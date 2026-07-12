#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PY:-$HOME/.venvs/telecom-agent/bin/python}"
F="infra/docker-compose/docker-compose.yml"
A="infra/docker-compose/docker-compose.apps.yml"
R="infra/docker-compose/docker-compose.rag.yml"
DC=(docker compose -f "$F" -f "$A" -f "$R")
OBJECT_KEY="phase3-smoke/flexi.md"

[[ -x "$PY" ]] || { echo "FAIL: missing Python environment: $PY"; exit 1; }
[[ -f .env ]] || { echo "FAIL: missing .env"; exit 1; }
[[ -f packages/persistence/alembic/versions/0010_knowledge_rag.py ]] || {
  echo "FAIL: Phase 1 migration is missing"; exit 1;
}
[[ -f packages/persistence/src/persistence/models/knowledge.py ]] || {
  echo "FAIL: Phase 1 knowledge ORM is missing"; exit 1;
}
grep -qE '^NVIDIA_API_KEY=.+$' .env || {
  echo "FAIL: NVIDIA_API_KEY is missing or empty"; exit 1;
}

echo "== Install and test Phase 3 =="
"$PY" -m pip install -q \
  ./packages/domain-core ./packages/persistence ./packages/service-auth \
  ./services/knowledge-service
"$PY" -m pytest -q \
  services/knowledge-service/tests/test_documents.py \
  services/knowledge-service/tests/test_phase2_infrastructure.py

echo "PHASE3_OFFLINE_TESTS_PASSED"

echo "== Start Postgres, Qdrant, and MinIO =="
"${DC[@]}" up -d postgres qdrant minio

for endpoint in \
  http://localhost:6333/readyz \
  http://localhost:9000/minio/health/ready; do
  ready=0
  for _ in {1..30}; do
    if curl -fsS --max-time 3 "$endpoint" >/dev/null; then ready=1; break; fi
    sleep 2
  done
  [[ "$ready" == 1 ]] || { echo "FAIL: dependency not ready: $endpoint"; exit 1; }
done

echo "RAG_INFRA_READY"

echo "== Apply persistence and bootstrap stores =="
(
  cd packages/persistence
  "$PY" -m alembic upgrade head
)

set -a
# shellcheck disable=SC1091
source .env
set +a
export MINIO_ENDPOINT="localhost:9000"
export MINIO_KNOWLEDGE_BUCKET="${MINIO_KNOWLEDGE_BUCKET:-telecom-knowledge}"
export QDRANT_URL="http://localhost:6333"
export QDRANT_COLLECTION="${QDRANT_COLLECTION:-telecom_knowledge}"
export EMBEDDING_DIMENSIONS="384"

knowledge-bootstrap-qdrant
knowledge-bootstrap-bucket

echo "STORAGE_BOOTSTRAP_PASSED"

echo "== Upload deterministic multilingual knowledge fixture =="
FIXTURE="$(mktemp)"
trap 'rm -f "$FIXTURE"' EXIT
{
  echo '# Offre Flexi'
  for _ in {1..90}; do
    echo 'L offre Flexi est un forfait mobile postpaye disponible en Tunisie avec appels, donnees et assistance client.'
  done
} > "$FIXTURE"

FIXTURE="$FIXTURE" OBJECT_KEY="$OBJECT_KEY" "$PY" - <<'PY'
import os
from pathlib import Path
from minio import Minio

path = Path(os.environ["FIXTURE"])
client = Minio(
    os.environ["MINIO_ENDPOINT"],
    access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)
bucket = os.environ["MINIO_KNOWLEDGE_BUCKET"]
client.fput_object(
    bucket,
    os.environ["OBJECT_KEY"],
    str(path),
    content_type="text/markdown; charset=utf-8",
    metadata={
        "title": "Offre Flexi",
        "language": "fr",
        "document-type": "product-guide",
        "applicable-plans": "flexi,premium",
        "product-codes": "FX1,FX2",
        "regions": "tn",
        "valid-from": "2026-01-01",
    },
)
print("MINIO_FIXTURE_UPLOADED")
PY

echo "== First ingestion =="
knowledge-ingest --object "$OBJECT_KEY"

DB_USER="${POSTGRES_USER:-telecom}"
DB_NAME="${POSTGRES_DB:-telecom}"

COUNTS_BEFORE="$(${DC[@]} exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -At -F, -c "
SELECT
  (SELECT count(*) FROM knowledge.documents WHERE source='$OBJECT_KEY'),
  (SELECT count(*) FROM knowledge.chunks c JOIN knowledge.documents d ON d.id=c.document_id WHERE d.source='$OBJECT_KEY'),
  (SELECT count(*) FROM knowledge.chunks c JOIN knowledge.documents d ON d.id=c.document_id WHERE d.source='$OBJECT_KEY' AND c.active),
  (SELECT count(*) FROM knowledge.sync_outbox o JOIN knowledge.chunks c ON c.id=o.aggregate_id JOIN knowledge.documents d ON d.id=c.document_id WHERE d.source='$OBJECT_KEY' AND o.status='succeeded');
")"
IFS=, read -r DOCS_BEFORE CHUNKS_BEFORE ACTIVE_BEFORE SYNCED_BEFORE <<< "$COUNTS_BEFORE"

[[ "$DOCS_BEFORE" -ge 1 ]] || { echo "FAIL: no document row"; exit 1; }
[[ "$CHUNKS_BEFORE" -ge 2 ]] || { echo "FAIL: expected overlapping chunks"; exit 1; }
[[ "$ACTIVE_BEFORE" == "$CHUNKS_BEFORE" ]] || { echo "FAIL: inactive new chunks"; exit 1; }
[[ "$SYNCED_BEFORE" == "$CHUNKS_BEFORE" ]] || { echo "FAIL: outbox/Qdrant sync incomplete"; exit 1; }

echo "POSTGRES_INGESTION_GATE_PASSED"

echo "== Second ingestion proves checksum idempotency =="
knowledge-ingest --object "$OBJECT_KEY"

COUNTS_AFTER="$(${DC[@]} exec -T postgres psql -U "$DB_USER" -d "$DB_NAME" -At -F, -c "
SELECT
  (SELECT count(*) FROM knowledge.documents WHERE source='$OBJECT_KEY'),
  (SELECT count(*) FROM knowledge.chunks c JOIN knowledge.documents d ON d.id=c.document_id WHERE d.source='$OBJECT_KEY');
")"
IFS=, read -r DOCS_AFTER CHUNKS_AFTER <<< "$COUNTS_AFTER"

[[ "$DOCS_AFTER" == "$DOCS_BEFORE" ]] || { echo "FAIL: duplicate document created"; exit 1; }
[[ "$CHUNKS_AFTER" == "$CHUNKS_BEFORE" ]] || { echo "FAIL: duplicate chunks created"; exit 1; }

echo "CHECKSUM_IDEMPOTENCY_GATE_PASSED"

echo "== Verify Qdrant payloads =="
QDRANT_COUNT_JSON="$(curl -fsS -X POST \
  "http://localhost:6333/collections/${QDRANT_COLLECTION}/points/count" \
  -H 'Content-Type: application/json' \
  -d "{\"filter\":{\"must\":[{\"key\":\"source\",\"match\":{\"value\":\"$OBJECT_KEY\"}},{\"key\":\"active\",\"match\":{\"value\":true}}]},\"exact\":true}")"
QDRANT_COUNT_JSON="$QDRANT_COUNT_JSON" EXPECTED="$ACTIVE_BEFORE" "$PY" - <<'PY'
import json
import os
payload = json.loads(os.environ["QDRANT_COUNT_JSON"])
count = int((payload.get("result") or {}).get("count", 0))
expected = int(os.environ["EXPECTED"])
if count != expected:
    raise SystemExit(f"FAIL: Qdrant has {count} active fixture points; expected {expected}")
print(f"QDRANT_ACTIVE_POINTS={count}")
print("QDRANT_INGESTION_GATE_PASSED")
PY

echo "RAG_PHASE3_GATE_PASSED"
