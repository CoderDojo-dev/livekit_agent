# RAG Architecture — Problems, Costs, and Complications

> This document is for the engineer. It lists every known problem in the current RAG
> pipeline, what causes it, what it costs, and what makes it hard to fix. It is organized
> by severity, not by phase.

---

## 1. The 1.1 GB Reranker Weight — Cost and Justification

### What was added

| Component | Model | Size | RAM | Where it lives |
|-----------|-------|------|-----|----------------|
| Bi-encoder (embedder) | `intfloat/multilingual-e5-small` | ~130 MB | ~0.3 GB | `/opt/models`, baked at build time |
| **Cross-encoder (reranker)** | **`jinaai/jina-reranker-v2-base-multilingual`** | **~1.1 GB** | **~1.1 GB** | **`/opt/models`, baked at build time** |
| **Total model weight in the container** | | **~1.4 GB** | **~1.4 GB** | |

### Why it was added

On the 16-document corpus, the bi-encoder's cosine scores inverted:
- Control query ("how do I fix my washing machine") scored **0.8411**
- Arabic true positive ("كيف أفعل التجوال الدولي") scored **0.8310**

The noise outranked the correct answer. No FLOOR threshold could separate them without
also dropping every Arabic answer. The cross-encoder reads query + passage together with
full attention, so it scores meaning instead of embedding shape — its noise ceiling
dropped to 0.0982 (16x reduction).

### What makes it complicated

- It is the **only multilingual reranker** fastembed ships. The 0.08 GB ms-marco models
  are English-only and cannot score a French or Arabic question at all.
- It runs **per candidate** — one forward pass for each of the 12 dense hits — so it is
  the dominant latency cost in the pipeline.
- It is **~1.1 GB of RAM** that is allocated for the entire lifetime of the container,
  even when no query is running. On a RAM-constrained host running multiple services
  (Postgres, Qdrant, MinIO, the agent worker, the voice pipeline), this competes.
- It cannot be lazy-loaded fast enough for the first query — the 118-second cold start
  is covered by the lifespan warmup, but if the container restarts mid-call, the first
  caller waits.

---

## 2. Latency — 2-5 Seconds Per Query

### The problem

| Stage | Time | What it does |
|-------|------|-------------|
| Dense retrieval (Qdrant ANN) | ~50ms | Embed query, search 257 vectors, return 12 candidates |
| Cross-encoder reranking (12 candidates) | **~2-5s** | 12 forward passes through a 1.1 GB ONNX model |
| **Total per `/search` call** | **~2-5s** | Synchronous — the agent waits |

### What causes the slowness

1. **CPU-only ONNX inference.** No GPU is available. The reranker model is a transformer
   with full cross-attention — each (query, passage) pair is tokenized, embedded, and run
   through multiple attention layers. On CPU, each pair takes ~200-400ms. 12 pairs =
   2.4-4.8s.

2. **No batching across pairs.** The reranker scores pairs sequentially (or in small
   batches depending on onnxruntime's internal batching). The 12 candidates are
   independent, so in principle they could be batched into one forward pass — but
   fastembed's `TextCrossEncoder.rerank()` does not expose batch-size control.

3. **The `KNOWLEDGE_SEARCH_TIMEOUT_S=5.0` is at the edge.** Warm queries take 2-5s.
   Some will exceed 5s and return `[]` (the Phase 6b timeout fix returns an empty list,
   not an error — but that is a false negative, not a fast answer).

### What makes it complicated

- **Reducing candidates reduces recall.** Lowering `KNOWLEDGE_RERANK_CANDIDATES` from 12
  to 8 cuts latency by ~33%, but a correct passage that the dense stage ranked #9-12
  becomes invisible to the reranker.
- **The voice pipeline needs sub-second response.** A 2-5s knowledge search on a live
  caller's line is unacceptable for voice. For chat, it is fine. The same RAG service
  serves both — there is no per-channel latency budget.
- **Moving reranking to a background worker would decouple it from the caller**, but that
  is a new architecture (queue + cache + stale-while-revalidate), not a config change.

---

## 3. Threshold Too High — French False Negative

### The problem

The default `KNOWLEDGE_RERANK_THRESHOLD=0.5` drops the French roaming query's correct
answer:

| Query | Correct passage | Rerank score | Threshold | Result |
|-------|----------------|-------------|-----------|--------|
| `comment activer le roaming a l'etranger` (FR) | `procedures/roaming-activation.md` | **0.3336** | 0.5 | **DROPPED — `[]` returned** |

The agent says "I have no information" for a question the corpus CAN answer.

### What causes it

The correct answer is in **English** (`roaming-activation.md`). The reranker compares a
French query to an English passage cross-lingually. Cross-lingual rerank scores run
systematically lower than same-language — the model's attention can match meaning across
languages, but the tokenization and vocabulary mismatch depress the score.

### What makes it complicated

The probe measured the safe threshold window:
- Control ceiling (noise): **0.0982**
- Lowest true positive (FR): **0.3336**
- Current threshold: **0.5** (above the true positive — wrong)

A threshold of **0.25** would sit between them. But:
- Adding more French documents would raise the FR true positive, widening the window.
- Adding more noise documents could raise the control ceiling, narrowing it.
- The threshold is a **single global value** — there is no per-language threshold. If a
  future Arabic query scores 0.20, a 0.25 threshold drops it. A 0.10 threshold admits
  noise. One number cannot serve all languages if their score ranges overlap.

---

## 4. Arabic Ranking — Correct Answer Not #1

### The problem

The Arabic roaming query returns 5 passages. The correct answer
(`roaming-activation.md`) ranks **#2**, not #1:

| Rank | Rerank score | Source | Correct? |
|------|-------------|--------|----------|
| 1 | 0.6342 | `faq/voice-call-problems.pdf` | Partial — mentions international calling |
| 2 | 0.5778 | `procedures/roaming-activation.md` | **YES — the actual procedure** |
| 3 | 0.5515 | `contracts/terms-fup-international-roaming.pdf` | Partial — roaming terms |
| 4 | 0.5112 | `offers/value-added-services.pdf` | Noise — VAS FAQ |
| 5 | 0.5041 | `contracts/terms-fup-international-roaming.pdf` | Partial — roaming terms |

### What causes it

The correct answer is a **1-chunk English document** (2 sentences, 40 words). The
voice-call-problems passage is a **17-chunk French document** with a long section on
international calling. The reranker gives higher scores to passages with more
overlapping vocabulary, so the longer passage wins on word-count even though it is less
precise.

### What makes it complicated

- The corpus has **no Arabic content**. The query is Arabic, the correct answer is
  English, the competing passage is French — the reranker is comparing across three
  languages simultaneously.
- Adding an Arabic version of `roaming-activation.md` would likely fix this, but it
  requires human translation and ingestion.
- The ranking is "acceptable" (the correct answer IS returned), but if the agent only
  reads the top passage, it will quote voice-call troubleshooting instead of the
  activation procedure.

---

## 5. Dense Stage Inversion (Bi-Encoder Fundamental Limit)

### The problem

The bi-encoder (E5) embeds the query and each passage independently, then compares the
vectors by cosine similarity. On the 16-document corpus this is **provably broken**:

| Query | Dense score | Correct? |
|-------|-----------|----------|
| "how do I fix my washing machine" (control) | **0.8411** | NOISE |
| "كيف أفعل التجوال الدولي" (Arabic, true positive) | **0.8310** | SIGNAL |

The noise (0.8411) outranks the signal (0.8310). This is not a tuning problem — it is
**structural to bi-encoders**. The control query is troubleshooting-shaped, and the
passages are troubleshooting-shaped, so the embeddings are close regardless of meaning.

### What causes it

- E5 is trained with a low-temperature (0.01) InfoNCE loss, so cosine scores compress
  into a narrow band (0.7-1.0). Everything looks similar.
- Cross-lingual pairs score systematically lower than same-language pairs, regardless of
  meaning. Arabic queries are penalized relative to English queries.
- A larger corpus has more "telecom-shaped" noise, so the noise floor rises uniformly.

### What makes it complicated

- This is **the reason the 1.1 GB reranker exists**. Without it, the gate cannot work on
  this corpus. The reranker is the cost of the bi-encoder's structural limit.
- Switching to a larger bi-encoder (`e5-base` instead of `e5-small`) would widen the
  headroom but would NOT fix the inversion — the structural compression is inherent to
  the training loss, not the model size.
- A hybrid retrieval approach (sparse + dense, e.g. BM25 + E5) would help the dense
  stage find the right documents, but would not fix the scoring inversion — BM25 does
  not produce calibrated scores either.

---

## 6. Corpus Content Gaps

### The problem

| What is missing | Impact |
|-----------------|--------|
| Prepaid Mobile (TRANKIL) description | The agent cannot answer "what is included in my prepaid plan" |
| Fibre Fixe (FIBER) description | The agent cannot answer "what is my fiber speed/price" |
| French version of `roaming-activation.md` | French queries get cross-lingual scores (0.33 instead of 0.7+) |
| Arabic content (any) | Arabic queries compare against English/French passages across 3 languages |
| Recharge catalog (R5/R10/R20/R50) details | The agent cannot answer "how much bonus do I get on a 20 TND recharge" |

### What causes it

The corpus was seeded with 5 English Markdown documents (Phase 3), then 13 French PDFs
were uploaded (Phase 5a). No Arabic content was ever added. The two mock offers (TRANKIL,
FIBER) are defined in seed code but are documented nowhere in the RAG corpus.

### What makes it complicated

- Adding content is easy (`POST /knowledge/upload` or edit `corpus.py`), but every new
  document **shifts the score distributions** and the threshold may need recalibration.
- Arabic content requires human translation — the PDFs are in French.
- The recharge catalog is structured data (table of amounts/bonuses), not prose — it
  needs to be converted to text for the embedder.

---

## 7. Single Global Threshold — Language Unfairness

### The problem

`KNOWLEDGE_RERANK_THRESHOLD` is one number for all languages. But the reranker's scores
are language-dependent:

| Language | True positive rerank score | Headroom over control (0.0982) |
|----------|---------------------------|-------------------------------|
| English | 0.7793 | +0.6812 |
| Arabic | 0.6342 | +0.5360 |
| French | 0.3336 | +0.2354 |

English has 3x more headroom than French. A threshold that works for English (0.5) drops
French. A threshold that works for French (0.25) admits noise for English (if the corpus
grows and the control ceiling rises).

### What causes it

The reranker is multilingual but not language-balanced. Same-language pairs score
higher than cross-lingual pairs because the tokenization and vocabulary overlap better.
French queries against English passages get the worst scores.

### What makes it complicated

- There is no per-language threshold mechanism in the current code. Adding one would
  require language detection on the query and a threshold lookup table — new code, not
  just config.
- The score ranges may **overlap** across languages as the corpus grows, meaning no
  per-language threshold can perfectly separate them either.
- The corpus is currently 80% French PDFs, 20% English MD, 0% Arabic. The score
  distributions reflect this imbalance.

---

## 8. Latency Timeout Race Condition

### The problem

`KNOWLEDGE_SEARCH_TIMEOUT_S=5.0` in the MCP tool. Warm reranker queries take 2-5s. Some
queries will exceed 5s and return `[]` — a false negative.

### What causes it

The reranker's latency varies with passage length (longer passages = more tokens = slower
forward pass). The 16-document corpus has passages ranging from 40 words (roaming-activation.md)
to 800+ words (PDF chunks). A query that reranks 12 long passages can exceed 5s.

### What makes it complicated

- **Raising the timeout** to 10s makes the agent wait longer on a live call.
- **Lowering candidates** to 8 reduces latency but drops recall.
- **The timeout and the candidates are coupled** — changing one affects the other's
  failure mode. There is no single value that is safe for all query/passage-length
  combinations.
- The MCP tool's timeout return `[]` is correct behavior (the agent says "I don't know"
  instead of crashing), but it is indistinguishable from a genuine "no information" — the
  agent cannot tell "timed out" from "nothing relevant."

---

## 9. Scanned PDFs — No OCR

### The problem

2 PDFs from the knowledge docs folder cannot be ingested:
- `billing invoicing account management.pdf`
- `mobile network sim troubleshooting.pdf`

Both are scanned images with no extractable text layer. `pypdf` extracts nothing. The
system rejects them with: "PDF contains no extractable text (scanned image? OCR is
required)."

> **Note:** The user later provided modified versions of these files that DID extract
> text. They were re-uploaded and ingested successfully (23 chunks each). The original
> scanned versions remain unusable.

### What causes it

`pypdf` extracts text from the PDF text layer. Scanned PDFs have no text layer — they are
images of pages. Extracting text from images requires OCR (e.g. Tesseract, PaddleOCR),
which is not in the pipeline.

### What makes it complicated

- Adding OCR (Tesseract) is ~200MB of additional dependencies + a language pack per
  language (eng, fra, ara). Arabic OCR is particularly unreliable.
- OCR text is noisy — it introduces typos, misreads tables, and drops formatting. This
  would add noise to the corpus and potentially lower retrieval quality.
- The two files were replaced by the user with text-based versions, so this is no longer
  blocking — but any future scanned PDF will hit the same wall.

---

## 10. PDF Encoding Artifacts

### The problem

Some French PDFs contain `?` characters where accented characters or special symbols
should appear (e.g. `conﬁrm` instead of `confirm`, `ﬁ` ligatures, `→` arrows). These
artifacts are in the ingested text and affect embedding quality.

### What causes it

`pypdf` does not always correctly decode PDF font encodings. Some PDFs use custom font
encodings where character code 0x01 maps to a ligature (`ﬁ`) or a symbol, and `pypdf`
either drops the character or replaces it with `?`.

### What makes it complicated

- The artifacts are in the stored text (Postgres + Qdrant + MinIO). Fixing them requires
  re-parsing and re-ingesting all affected documents.
- A different PDF library (`pdfplumber`, `pymupdf`) might handle the encodings better, but
  switching libraries changes all extracted text and requires re-ingesting everything.
- The artifacts do not break retrieval (the embeddings are robust to small text noise),
  but they are visible in the passages shown to the agent and the caller.

---

## 11. Container Cold Start — 118 Seconds for Model Load

### The problem

The first `/search` call after a container restart takes ~118 seconds because the 1.1 GB
reranker ONNX session must load into RAM. This is covered by the lifespan warmup (the
model loads at startup, not on the first query), but if the container crashes and
restarts mid-conversation, the recovery time is 2 minutes.

### What causes it

ONNX Runtime loads the model weights from disk into RAM, initializes the compute graph,
and warms up the CPU threads. For a 1.1 GB transformer model on CPU, this is slow.

### What makes it complicated

- The `HEALTHCHECK --start-period=60s` covers the embedder (~30s) but not the reranker
  (~90s more). The container will report "unhealthy" and may be restarted by Docker
  before the reranker finishes loading — causing a crash loop.
- Increasing `--start-period` to 180s delays startup but prevents the crash loop.
- The reranker is loaded in the `lifespan` startup, so the first query does not pay the
  cost — but the container is not ready to serve until it finishes.

---

## 12. Reranker Failure Mode — No Graceful Degradation

### The problem

If the reranker fails (ONNX load error, OOM, corrupted model file), `/search` returns
503. There is no fallback to the dense gate. The agent gets nothing.

### What causes it

This is **by design**. The patch comment says: *"On reranker failure this raises rather
than falling back to the cosine gate. That gate is measurably broken on this corpus — the
control query sails through it — so falling back would feed the agent confident noise."*

The decision is correct: a silent downgrade to a broken gate is worse than an honest 503.
But it means the reranker is a **single point of failure** for the entire knowledge
service.

### What makes it complicated

- If the host runs out of RAM (1.1 GB for the reranker + everything else), the ONNX
  session may fail to load, and the service goes down.
- There is no health-detection for "reranker loaded but slow" — a degraded reranker that
  takes 30s per query will cause timeouts but will not fail the health check.
- A smaller fallback reranker (English-only ms-marco, 0.08 GB) could serve as a degraded
  path for English queries, but it cannot score French or Arabic at all.

---

## 13. No Query Language Detection

### The problem

The pipeline does not detect the query language. The embedder applies the `query: ` prefix
uniformly. The reranker scores pairs without knowing the language. The threshold is global.

### What causes it

Language detection was never added because the 5-document corpus was English-only. The
16-document corpus is 80% French, 20% English, and receives Arabic queries — but the code
treats all queries the same.

### What makes it complicated

- Adding language detection (e.g. `langdetect`, `fasttext-lang`) is cheap (~1ms) and
  would enable: per-language thresholds, language-specific filters in the dense stage
  (only search French passages for a French query), and better debugging.
- But it introduces a new failure mode: if the detector misidentifies the language, the
  filters exclude the correct passage entirely (worse than a low score).
- Arabic detection is reliable. French/English confusion is the main risk — and the
  corpus has English documents that French queries should be able to find.

---

## 14. Over-Fetch vs. Top-k Mismatch

### The problem

The dense stage fetches `max(top_k, 12)` candidates when the reranker is enabled. If the
caller asks for `top_k=4`, the dense stage fetches 12, the reranker scores all 12, and 4
are returned. But if the caller asks for `top_k=20`, the dense stage fetches 20, and the
reranker scores 20 — 20 forward passes, ~8-10 seconds.

### What causes it

`limit = max(top_k, rerank_candidates())` — the dense stage fetches at least
`rerank_candidates` (12), but if `top_k` is higher, it fetches `top_k`. The reranker then
scores ALL of them.

### What makes it complicated

- The MCP tool calls `/search` with `top_k=5` (default), so this is not a problem in
  practice. But a future caller requesting `top_k=50` would trigger 50 forward passes.
- Capping the rerank candidates at `rerank_candidates()` regardless of `top_k` would fix
  this, but then `top_k=50` returns only 12 reranked passages — the rest are ungated
  dense results, which are noise.

---

## 15. Mock Seed Data — Confusing but Not Broken

### The problem

Three mock telecom offers (FLEXI, TRANKIL, FIBER) exist in `reference.products` and 4
recharges in `reference.recharge_catalog`. No production code reads these tables at
runtime. The pilot clients' `plan_code` values ("Postpaid Flexi", "Prepaid Mobile",
"Fibre Fixe") are stored strings in `crm.subscriptions`, not foreign keys to
`reference.products`.

### What causes it

The seeds were created for early development before the RAG pipeline existed. The RAG
corpus (corpus.py + Qdrant) is now the authority for offer descriptions, but the old seed
tables were never removed.

### What makes it complicated

- It is **not broken** — the system works correctly with the seeds present or absent.
- But it is **confusing** for a new engineer who sees Product models, reference tables,
  and seed scripts and assumes they are load-bearing.
- The `change_plan` tool accepts any string — it does not validate against the database.
  So "Postpaid Flexi" works whether or not the seed exists.
- The RAG corpus only documents the Flexi plan (1 document). Prepaid Mobile and Fibre
  Fixe are not documented anywhere in the RAG corpus, so the agent cannot describe them
  even though the pilot clients have them.

---

## Summary — What Makes Everything Complicated

| Root cause | What it breaks | What it costs to fix |
|-----------|---------------|---------------------|
| Bi-encoder cosine compression (structural) | Noise inversion on 16-doc corpus | 1.1 GB reranker + 2-5s latency |
| Cross-lingual score depression (structural) | French false negative, Arabic mis-ranking | Add FR/AR content + per-language threshold |
| CPU-only inference (infrastructure) | 2-5s per query, 118s cold start | GPU (not available) or smaller model (English-only) |
| Single global threshold (code) | One number cannot serve 3 languages | Per-language threshold (new code) |
| No OCR (pipeline gap) | Scanned PDFs rejected | Add Tesseract (~200MB + language packs) |
| No language detection (code gap) | Cannot apply per-language logic | Add langdetect (~1ms, new failure mode) |
| Corpus imbalance (content gap) | 80% FR, 20% EN, 0% AR | Add Arabic + missing offers |
| PDF encoding artifacts (library limit) | `?` characters in passages | Switch PDF library + re-ingest everything |
| Reranker is SPOF (architecture) | Service down if reranker fails | No safe fallback (the dense gate is broken) |
| Timeout vs. latency race (config) | Some queries return `[]` (false negative) | Tune candidates + timeout (coupled trade-off) |

### The honest bottom line

The RAG pipeline works, but it is **fitted to a specific corpus at a specific point in
time**. Every threshold (FLOOR, RELATIVE, RERANK_THRESHOLD) is calibrated against 16
documents. Adding documents, changing languages, or growing the corpus will shift the
score distributions and the thresholds will need re-tuning. The probe
(`scripts/knowledge_score_probe.py`) is the only tool that can tell you when that
happens — run it after every corpus change.

The 1.1 GB reranker is the cost of fixing a problem that is structural to bi-encoders.
It is not optional on this corpus. The latency it introduces (2-5s) is the price of
correctness. If that price is too high for the voice pipeline, the options are: a
smaller corpus (fewer noise documents), a monolingual corpus (English-only, use the 0.08
GB reranker), or a GPU (not available on this host).
