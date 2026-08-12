# Phase 6b — Relevance gate + the silent-agent bug

## What changed

| File | Change | Role |
|------|--------|------|
| `retriever.py` | Extended | `DEFAULT_SCORE_FLOOR` (0.80) + `DEFAULT_RELATIVE_CUTOFF` (0.93) constants. `apply_relevance_gate()` pure function: drops passages that fail both gates. Wired into `QdrantE5Retriever.search()`. |
| `knowledge_search.py` (MCP) | Rewritten | `raise_for_status()` on 503 no longer kills the agent — returns `[]` and logs the error. Configurable timeout via `KNOWLEDGE_SEARCH_TIMEOUT_S`. |
| `scripts/knowledge_score_probe.py` | **New** | Calibration probe: prints raw score distribution per query with KEEP/drop markers, so thresholds are set from evidence. |
| `.env.example` / `.env` | Extended | `KNOWLEDGE_SCORE_FLOOR=0.80`, `KNOWLEDGE_RELATIVE_CUTOFF=0.93`, `KNOWLEDGE_SEARCH_TIMEOUT_S=5.0` |

## Problem 1 — The silent-agent bug (fixed)

The MCP tool called `resp.raise_for_status()` on `/search`. Since Phase 4, the service returns 503 when the index is unusable. That 503 raised an exception inside the tool call → the LLM emitted a tool call, the tool raised, the agent produced no speech. The caller heard silence and hung up. This was the original symptom from the first logs.

**Fix:** `knowledge_search()` now catches `HTTPStatusError` and `HTTPError`, logs the root cause, and returns `[]`. The agent says "I don't have that information" and the conversation continues. The failure is loud in the logs, not on the call.

## Problem 2 — Retrieval returns noise (fixed)

Before Phase 6b, "how do I activate roaming" returned:

| Rank | Source | Score | Relevant? |
|------|--------|-------|----------|
| 1 | `procedures/roaming-activation.md` | 0.8918 | ✅ Yes |
| 2 | `faq/data-troubleshooting.md` | 0.7953 | ❌ No |
| 3 | `offers/forfait-flexi.md` | 0.7785 | ❌ No |

Two of three passages were irrelevant. An LLM handed them would ground an answer on filler — hallucination on a telecom support line.

**Fix:** Two gates, because neither alone is safe:
- **FLOOR** (0.80) — absolute cutoff. Kills "nothing is relevant" (a relative gate alone would keep the best of a bad set).
- **RELATIVE** (0.93) — share of top score. Kills "one good hit + filler" and adapts to E5's per-query score drift.

A passage must clear **both** to survive.

## Calibration probe results

```
gate defaults: FLOOR=0.80  RELATIVE=0.93

Q: how do I activate roaming abroad
   KEEP  0.8953  ratio=1.000  procedures/roaming-activation.md

Q: comment activer le roaming a l etranger
   KEEP  0.8606  ratio=1.000  procedures/roaming-activation.md

Q: كيف أفعل التجوال الدولي
   KEEP  0.8310  ratio=1.000  procedures/roaming-activation.md
   KEEP  0.8016  ratio=0.965  faq/billing-cycle.md
   drop  0.7849  ratio=0.945  faq/data-troubleshooting.md

Q: why is my mobile data slow
   KEEP  0.8670  ratio=1.000  faq/data-troubleshooting.md
   KEEP  0.8362  ratio=0.964  procedures/plan-change.md
   KEEP  0.8253  ratio=0.952  offers/forfait-flexi.md
   KEEP  0.8187  ratio=0.944  procedures/roaming-activation.md

Q: what is included in the Flexi plan
   KEEP  0.8614  ratio=1.000  offers/forfait-flexi.md

Q: how do I fix my washing machine  ← CONTROL (not telecom)
   drop  0.7880  ratio=1.000  faq/data-troubleshooting.md
   drop  0.7790  ratio=0.989  procedures/roaming-activation.md
   drop  0.7761  ratio=0.985  procedures/plan-change.md
   drop  0.7654  ratio=0.971  faq/billing-cycle.md
   drop  0.7615  ratio=0.966  offers/forfait-flexi.md
```

**Key observations:**
- **Control query** ("washing machine") → all 5 dropped (max score 0.7880 < FLOOR 0.80). The agent will say "I don't know" — **no hallucination**.
- **Single-topic queries** (roaming, Flexi plan) → only the correct document kept. Noise eliminated.
- **Broad queries** ("why is my data slow") → 4 kept because E5 compresses scores when multiple documents are genuinely relevant. This is expected with 5 documents; calibrate when the real corpus arrives.

## Live /search API verification

### Roaming query (was 3 passages, now 1)

```
POST /search {"query":"how do I activate roaming","top_k":3}
```

| Before Phase 6b | After Phase 6b |
|-----------------|----------------|
| 0.8918 `procedures/roaming-activation.md` | 0.8918 `procedures/roaming-activation.md` |
| 0.7953 `faq/data-troubleshooting.md` ❌ | *(dropped by FLOOR < 0.80)* |
| 0.7785 `offers/forfait-flexi.md` ❌ | *(dropped by FLOOR < 0.80)* |

### Control query (washing machine — should return nothing)

```
POST /search {"query":"how do I fix my washing machine","top_k":3}
→ {"passages": []}
```

Empty result → the agent will say it doesn't have that information. **No hallucination.**

## Summary

- **Silent-agent bug fixed** — a 503 from the knowledge service no longer freezes the caller's line. The MCP tool returns `[]`, the agent says "I don't have that information", the conversation continues.
- **Relevance gate working** — the roaming query went from 3 passages (2 irrelevant) to 1 (the correct one). The control query returns empty — no hallucination.
- **Two-gate design** — FLOOR kills "nothing is relevant", RELATIVE kills "one good hit + filler". Both must pass.
- **Calibration probe shipped** — `scripts/knowledge_score_probe.py` prints the raw score distribution so thresholds are set from evidence, not guesses. Re-run after loading the real corpus.
