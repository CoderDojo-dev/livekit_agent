# Version 59 — Geo-referenced Zone Resolution + NMS Honesty Overhaul

> **Base branch:** `version_58`
> **Files changed:** 23 (+1280 / -73) — 13 modified + 10 new
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)

---

## Containers & SDK

| Item               | Change                  |
|--------------------|-------------------------|
| New containers     | None                    |
| livekit-agents SDK | `1.6.5` (unchanged)     |

---

## What's New

This version addresses five systemic problems in the network-status verification pipeline, codenamed Problems #1–#5:

| # | Problem | Symptom | Root Cause | Fix |
|---|---------|---------|------------|-----|
| 1 | No canonical zone referential | Same area stored under different spellings | `Outage.area` was free text | `GeoArea` + `GeoAlias` tables with normalized search keys |
| 2 | Agent can't explain what's happening | Generic "known incident" with no cause/description | `Outage` had no description columns | Added `cause`, `description_fr/ar/en` to `Outage` |
| 3 | Zone-free outages match every query | A null-area outage appeared for any caller's area | `('' in needle)` is always `True` in Python | FK `area_code` → `GeoArea.area_code` (can't create zone-free outages) |
| 4 | Unresolvable areas reported as "operational" | Agent says network is fine for unrecognized places | Single status dimension | Four honest states: `area_unknown` / `operational` / `incident` / `unavailable` |
| 5 | Mock adapter fabricates "operational" | Agent claims network checked when no data source configured | `MockNmsAdapter` hardcoded `operational` | Returns `unavailable` with `verified=False` + reason |

### Geo Referential (`reference.geo_areas` + `reference.geo_aliases`)

**`GeoArea`** — Canonical Tunisian zone table with 24 governorates + 53 delegations. Each zone has an `area_code` (e.g. `TN-71-METLAOUI`), names in FR/AR/EN, an `area_type` (governorate/delegation/locality), and a `parent_code` FK to its parent zone.

**`GeoAlias`** — Every written or spoken form that resolves to a zone. The `normalized` column is a deterministic key (NFKD-decomposed, stripped of Arabic marks, articles removed) computed at write time and indexed with GIN trigram for fuzzy search.

**`geo_resolver.py`** — Three-stage zone resolver:
1. **Exact** — equality on `geo_aliases.normalized` (indexed, O(1))
2. **Compact** — equality on normalized key with spaces removed (handles compound names said as one word)
3. **Fuzzy** — pg_trgm `similarity()` above `GEO_MATCH_THRESHOLD` (default 0.45), for misspellings

Returns `ResolvedArea` with exact/approximate flag, or `None` when nothing crosses the threshold.

### Honest Network Status (`incidents.py`)

Complete rewrite with four mutually exclusive states:

| Status | `verified` | `incident_found` | Meaning |
|--------|-----------|-----------------|---------|
| `area_unknown` | `False` | — | Zone not in referential → nothing checked |
| `unavailable` | `False` | — | NMS unreachable → nothing checked |
| `operational` | `True` | `False` | Zone resolved, no active incidents → honest "all clear" |
| `incident` | `True` | `True` | Active incidents found with descriptions |

**Incident scope resolution**: Recursive SQL traverses ancestor zones (a governorate outage covers its delegations) and descendant zones (a delegation outage also affects it). Each incident is tagged as `covering` (confirmed) or `partial` scope.

### Incident Descriptions

`Outage` now has:
- `cause` — enumerated: `fiber_cut`, `power_failure`, `equipment_failure`, `planned_maintenance`, `congestion`, `weather`, `third_party_damage`
- `description_fr/ar/en` — free-text cause explanation in three languages

The `check_network_status` tool returns `cause`, `description`, `affected_services`, `severity`, `eta` for each incident. The agent's instructions (`technical_agent.py`) mandate truthful reporting: only say "network is normal" when `did_verified=True` and `incident_found=False`.

### Deepgram Keyterms for Better Transcription

Place names are notoriously mistranscribed by ASR. The new pipeline:
1. `GET /geo-keyterms` endpoint on nms-sim fetches zone names from the referential
2. `server.py` calls it at agent startup, filtered by `STT_KEYTERM_SCOPE` env var (pilot governorates)
3. `stt.py` passes them as Deepgram `keyterms` parameter (with version-safety check via `inspect.signature`)
4. Result: Deepgram is primed to recognize "Metlaoui", "Redeyef", etc.

### Service URL Collision Guard

`settings.py` now has a Pydantic `model_validator` that checks all service URLs for duplicates at startup. This caught `BUSINESS_API_URL` and `NMS_SERVICE_URL` both pointing at `:8108`. Fixed: `BUSINESS_API_URL` → `:8107`.

### New Scripts

| Script | Purpose |
|--------|---------|
| `scripts/seed_geo.py` | Populate `geo_areas` + `geo_aliases` from the Tunisian zone list (idempotent) |
| `scripts/seed_test_outages.py` | Insert 9 demo incidents across Gafsa/Sousse/Monastir (`ALLOW_TEST_DATA=1`) |
| `scripts/backfill_outage_area_code.py` | Resolve `area_code` for existing outages without one; logs unresolved for operator action |

### New Tests

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_geo_resolver.py` | 3 | normalize determinism, unknown returns None, misspelling resolves approximately |
| `tests/test_network_status_honesty.py` | 6 | unknown area, empty area, null-area outage, incident description, governorate coverage |
| `tests/test_nms_adapter_honesty.py` | 1 | Mock adapter returns unavailable, not operational |
