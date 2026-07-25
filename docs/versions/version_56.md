# Version 56 — French-native Retriever Tests & Honest-failure Notification Test

> **Base branch:** `version_55`
> **Files changed:** 70 (+28 / -4754) — 2 test file modifications + 68 stale files deleted

---

## Containers & SDK

| Item                | Change |
|---------------------|--------|
| New containers      | None   |
| livekit-agents SDK  | No bump|

---

## What's New

### Lexical Retriever Test Fix

The `test_retriever.py` offline tests were using **English** queries against a **French-native corpus**. The `LexicalRetriever` is a term-overlap BM25 stub for offline tests — it cannot do cross-lingual retrieval (that's the dense E5 path in production). English queries had zero overlap with French corpus terms, so the tests were effectively passing with empty results.

- Queries changed from English to French:
  - `"how do I activate international roaming abroad"` → `"comment activer l'itinérance internationale à l'étranger"`
  - `"when is my invoice due"` → `"consulter le montant et la date d'échéance de ma facture"`

### Honest-failure Notification Test

The old `test_notify_sends_and_records` tested a happy-path mock send that no longer exists (all mocks were removed in v46). Replaced with a real contract test:

- **`test_notify_without_live_channel_reports_honest_failure`**: with no Twilio/SMTP configured (keys removed from environment), the service must NOT fake a send.
- Asserts: `sent=False`, `reference=""`, a non-empty `reason`, the attempt is recorded in `service.sent`, and `sent` is `False` in the record.
- No mocks, no stubs — exercises the real render → channel → record pipeline.

### Stale Artifact Cleanup

Removed ~68 files of accumulated stale artifacts:

| Category | Files | Reason |
|----------|-------|--------|
| `BRANCH_VERSION_*.md` (v17–v51) | 34 files | Superseded by `docs/versions/` |
| `commands.md` | 1 file | Stale dev doc |
| `RAG_PHASE8*_REPORT.md`, `results.md` | 3 files | Stale result docs |
| `fixes/` directory | 30 files | Stale temp workspace |