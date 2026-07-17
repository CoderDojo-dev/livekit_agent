# Honest Answers — RAG Pipeline Phases 1-7

## Q1: Is everything now fixed when we applied patch 7?

**No.** Patch 7 fixed the most critical problem — the noise inversion where a non-telecom
question ("how do I fix my washing machine") outranked the correct Arabic answer — but the probe
immediately exposed a new one: the default rerank threshold (0.5) is too high for cross-lingual
queries, so the French roaming question returns zero results (its true positive scored 0.3336).
The probe's own calibration guidance says to lower the threshold to between 0.0982 (the control
ceiling) and 0.3336 (the lowest true positive) — i.e. ~0.25. That is a one-line `.env` change,
not a new phase, but it has not been made yet.

## Q2: Is the system now running perfectly?

**No, and it never will be — calibration is a moving target.** What is running:

- The control query correctly returns `[]` (noise eliminated).
- The English queries return the right passages.
- The Arabic query returns the correct answer (but ranked #2, not #1).
- The French roaming query returns `[]` — a false negative caused by the threshold.
- Each query takes 2-5 seconds after warmup, which is right at the edge of the 5s
  `KNOWLEDGE_SEARCH_TIMEOUT_S` and will occasionally time out.

"Perfectly" would require: lowering the threshold, adding French/Arabic content so
same-language queries score higher, and confirming latency is acceptable for the voice
pipeline. None of that is done yet.

## Q3: What's remaining in RAG implementation after phases 1-7?

1. **Lower `KNOWLEDGE_RERANK_THRESHOLD` from 0.5 to ~0.25.** The probe measured the safe
   window: control ceiling 0.0982, lowest true positive 0.3336. A threshold of 0.25 sits
   between them. This fixes the French false negative. One line in `.env`.

2. **Add French and Arabic content to the corpus.** The French false negative is partly
   because the correct answer (roaming-activation.md) is in English. A French version would
   score higher on a French query. Same for Arabic — the correct answer ranks #2 because the
   reranker is comparing a French passage to an Arabic question cross-lingually.

3. **Add the missing Prepaid Mobile (TRANKIL) and Fibre Fixe (FIBER) descriptions** to the
   corpus. They are documented nowhere — not in the PDFs, not in the MD files.

4. **Confirm latency is acceptable for the voice pipeline.** 2-5s per query is a long time
   on a caller's line. May need to reduce `KNOWLEDGE_RERANK_CANDIDATES` from 12 to 8, or pin
   `KNOWLEDGE_RERANKER_THREADS`.

5. **Decide on seed cleanup.** The mock seeds (`reference.products`,
   `reference.recharge_catalog`) are never read at runtime. Keep or remove — they are
   inoffensive either way.

6. **Re-run the probe after any corpus change.** Every threshold here is fitted to 16
   documents. Adding documents shifts the score distributions. The probe is the only way to
   know if the threshold still separates noise from signal.

## Q4: Is the last 1.1GB model necessary, and why?

**Yes, on this corpus it is necessary.** The evidence:

- On the 16-document corpus, the bi-encoder (E5) gave the control query ("how do I fix my
  washing machine") a score of 0.8411 — higher than the correct Arabic answer (0.8310).
- The noise outranked the signal. No FLOOR threshold could drop the noise without also
  dropping every Arabic answer.
- The bi-encoder embeds the query and each passage independently, so it can only compare
  two summaries — "washing machine" lands next to "wifi router" because the *shape*
  (troubleshooting prose) matches.
- The cross-encoder reads the query and passage TOGETHER with full attention, so it sees
  that "washing machine" is not "wifi router". Its noise ceiling dropped to 0.0982 — a
16x reduction.

The 1.1GB is the cost of fixing a problem that is provably unfixable without it. It is
the only multilingual reranker fastembed ships (the 0.08GB ms-marco models are
English-only and cannot score a French or Arabic question at all).

If the corpus were smaller (5 documents) or monolingual (English only), the 1.1GB
would NOT be necessary — the Phase 6c thresholds would still work. It became necessary
because the corpus grew to 16 multilingual documents.

## Q5: What's the latency of the RAG now?

Measured on the real corpus, 10 candidates per query, after the model is warm:

| Stage | Time |
|-------|------|
| Dense retrieval (Qdrant ANN) | ~50ms |
| Cross-encoder reranking (10 candidates) | ~2-5s |
| **Total per /search call** | **~2-5s** |
| First query after restart (model load) | ~118s (covered by startup warmup) |

The reranker is 40-100x slower than the dense stage. It is the dominant cost in the
pipeline.

## Q6: Can the agent not receive additional latency from that? And from retrieval?

**The agent WILL receive the additional latency — there is no way around it.** The
reranker runs synchronously inside `/search`. The agent calls `knowledge_search`, waits
for the response, then proceeds. There is no async/queue path.

The current `KNOWLEDGE_SEARCH_TIMEOUT_S=5.0` is right at the edge:
- Warm queries take 2-5s — some will time out.
- A timeout returns `[]` to the agent (the Phase 6b fix), so the agent says "I have no
  information" instead of crashing — but that is a false negative, not a fast answer.

Options to reduce the agent-visible latency:
1. **Reduce `KNOWLEDGE_RERANK_CANDIDATES` from 12 to 8** — fewer forward passes, faster,
   but lower recall (a correct passage ranked #9-12 becomes invisible).
2. **Pin `KNOWLEDGE_RERANKER_THREADS`** to dedicate CPU if the reranker competes with
   the voice pipeline.
3. **Raise `KNOWLEDGE_SEARCH_TIMEOUT_S`** to 10s — the agent waits longer but gets the
   answer.
4. **Move the reranker to a background worker** with a cache — but that is a new
   architecture, not a config change.

The honest answer: the agent will feel 2-5 seconds of additional latency on every
knowledge search. Whether that is acceptable depends on the caller experience
requirements. For a voice pipeline, it may be too slow.

## Q7: What's next?

In priority order:

1. **Lower `KNOWLEDGE_RERANK_THRESHOLD` to 0.25** (fixes French false negative).
2. **Test latency under realistic agent load** — confirm 2-5s is acceptable or tune
   candidates/threads.
3. **Add French/Arabic content** to the corpus (improves cross-lingual recall).
4. **Add Prepaid Mobile + Fibre Fixe descriptions** (the two missing offers).
5. **Re-run the probe** after any corpus change to re-verify the threshold.
6. **Decide on seed cleanup** (mock products/recharge catalog — keep or remove).

## Q8: Is phase 7 necessary, and why? Or are phases 1-6 enough?

**On the 16-document corpus, Phase 7 is necessary. On the 5-document corpus, it is not.**

The decision is purely evidence-based:

- **5-document corpus (Phases 3-6c):** The control query scored 0.7880, the Arabic true
  positive scored 0.8310. The FLOOR (0.80) sat between them. The gate worked. Phase 7 is
  unnecessary overhead (1.1GB + 2-5s latency) for a problem that does not exist.

- **16-document corpus (Phase 7):** The control query scored 0.8411, the Arabic true
  positive scored 0.8310. The noise outranked the signal. No FLOOR could separate them.
  The gate was broken. Phase 7 is the fix.

The trigger was corpus growth. If the corpus stays at 5 documents, Phase 7 is wasted
resources. If it grows past ~10 documents, Phase 7 is mandatory. The current corpus is
16 documents, so Phase 7 is necessary.

## Q9: What will we lose if we don't apply Phase 7 (stay at Phase 6c)?

If you disable the reranker (`KNOWLEDGE_RERANKER_ENABLED=false`) and stay on the Phase 6c
dense gate:

1. **The hallucination guard breaks.** The control query ("how do I fix my washing
   machine") returns 5 telecom passages with scores 0.82-0.84 — all above FLOOR=0.80.
   The agent will confidently answer a washing machine question from wifi-router
   troubleshooting prose.

2. **Arabic answers disappear or noise leaks through.** The Arabic true positive (0.8310)
   is below the noise ceiling (0.8411). Any FLOOR high enough to drop the noise (0.85+)
   also drops every Arabic answer. Any FLOOR low enough to keep Arabic (0.80) admits the
   noise. There is no safe value.

3. **You save 1.1GB RAM and 2-5s latency.** That is the trade-off. On a RAM-constrained
   host or a latency-sensitive voice pipeline, this matters. But you trade correctness
   for speed — the agent will answer confidently from noise.

The honest summary: without Phase 7, the agent cannot safely say "I don't know" on this
corpus. It will invent answers from irrelevant passages. That was the exact failure
mode the whole gate was built to prevent.

## Q10: What is a reranker?

A reranker is a second-stage model that re-scores the results of a first-stage retrieval
system. In this pipeline:

```
Stage 1 (bi-encoder / dense retrieval):
  Query -> embed into a vector
  Each passage -> pre-embedded into a vector
  Compare vectors by cosine similarity (fast, ~50ms)
  Returns top-N candidates (cheap, scalable, but shallow)

Stage 2 (cross-encoder / reranker):
  Take each (query, passage) pair TOGETHER
  Feed both through the model with full cross-attention
  The model sees every word of the query next to every word of the passage
  Output: a relevance score (slow, ~2-5s for 10 pairs, but precise)
```

The key difference: a bi-encoder compares two *summaries* (the query vector and the
passage vector, computed independently). A cross-encoder compares the *actual text*
together, so it can see that "washing machine" is not "wifi router" even though both are
troubleshooting prose.

Analogy: a bi-encoder is like matching two people by their dating profiles (independent
summaries). A cross-encoder is like putting them in the same room and watching them
talk (full interaction). The second is far more accurate but far more expensive.

The reranker does not replace the bi-encoder — it refines its output. The bi-encoder
does the fast initial filtering (257 chunks -> 12 candidates), and the reranker does
the slow precise scoring (12 candidates -> ranked, filtered list). This two-stage
design is standard in production RAG systems.
