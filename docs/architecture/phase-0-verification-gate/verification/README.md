# Phase 0 — Verification & Decision Gate (evidence)

Primary deliverable: **`00-DECISION-RECORD.md`** (the written decision record).

This `verification/` folder makes the decision reproducible, not asserted:

- `provider_matrix.py` — the decided per-language routing as pure data (one source of
  truth the Phase-1 `apps/agent-worker/src/providers/` wiring mirrors).
- `test_provider_matrix.py` — offline consistency tests (no keys/network/SDK).
- `verify_providers.py` — empirical per-language STT/TTS round-trip via direct LiveKit
  plugins (run in Phase 1 with real keys).

## Run the offline decision tests (no keys needed)
```bash
cd docs/architecture/phase-0-verification-gate/verification
python -m pytest -q .
```

## Reproduce the empirical go/no-go (Phase 1, with keys)
```bash
pip install -r requirements-spike.txt
cp .env.example .env   # fill in real keys
set -a && . ./.env && set +a
python verify_providers.py --languages fr ar en
```
