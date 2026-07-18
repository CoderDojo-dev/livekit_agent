# version_42 — P0 Fix: Calibration Probe Decoupling

## What's Fixed

### P0: `ce_top1` measured the wrong variable for CE gate threshold calibration
The Phase 8.1 calibration probe (`scripts/knowledge_score_probe.py`) was reporting `ce_top1` as the CE score of the **ungated dense top-1 passage**. But that's NOT the passage the gate evaluates — the gate first RRF-fuses dense+sparse survivors, then CE-scores *those* passages. The dense top-1 and the RRF-fused top-1 are often different passages, so calibrating the threshold against `ce_top1` was systematically wrong.

**Fix:** The probe now replicates the gate's intermediate pipeline state:
1. Dense search with `score_threshold = FLOOR` (same as the gate)
2. Sparse BM25 search
3. RRF fuse to `ce_max_candidates` width (same as the gate)
4. CE-score the actual fused survivors → `ce_max_kept`

New columns in the calibration table:
- `ce_max_kept` — the max CE score among the RRF-fused survivors (the gate's actual decision variable)
- `fused_n` — how many passages the CE gate evaluated (diagnoses P1 candidates-drop issue)

Summary and calibration help text now point at `ce_max_kept`, not `ce_top1`. A new "P0 diagnostic" section prints queries where `ce_top1 != ce_max_kept` (delta > 0.01).

## No Container / SDK Changes
This version contains no Dockerfile, docker-compose, pyproject.toml, or LiveKit SDK changes. It is purely a probe calibration fix.

## Files Changed
| File | Status | Description |
|------|--------|-------------|
| `scripts/knowledge_score_probe.py` | MODIFIED | P0 fix: decouple ce_top1 from ce_max_kept; replicate gated pipeline state; add fused_n diagnostic |
