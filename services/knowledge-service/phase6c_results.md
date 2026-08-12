# Phase 6c — Evidence-Based Gate Retune

## Summary

Phase 6c retunes the relevance gate based on probe data from the REAL corpus. The patch makes
three fixes: (1) a bug in the probe that was reporting gated scores as raw, (2) the RELATIVE
cutoff from 0.93 to 0.97, and (3) documents the structural language asymmetry (Arabic has 2.5x
less headroom than English). The probe was then re-run against the full 16-document / 257-chunk
corpus, producing the calibration data that determines the next steps.

---

## 1. Patch Implementation

### 1.1 Files Modified

| File | Change |
|------|--------|
| `.env.example` | `KNOWLEDGE_RELATIVE_CUTOFF` 0.93 -> 0.97; calibration comments rewritten |
| `.env` | `KNOWLEDGE_RELATIVE_CUTOFF` 0.93 -> 0.97 |
| `scripts/knowledge_score_probe.py` | Full rewrite: uses `apply_gate=False` bypass; per-language margins; control ceiling analysis |
| `services/knowledge-service/src/knowledge_service/retriever.py` | `DEFAULT_RELATIVE_CUTOFF` 0.93 -> 0.97; `apply_gate: bool = True` parameter on both `LexicalRetriever.search` and `QdrantE5Retriever.search`; ungated bypass block; calibration comments rewritten |

### 1.2 The Three Fixes

**Fix 1 — Probe bug (was lying):**
`search(min_score=0.0)` only zeroes the FLOOR; RELATIVE=0.93 still filtered. Every passage below
ratio 0.93 was never shown, so what looked like "raw scores" was already gated. Calibrating from
a gated sample is how you end up trusting a gate that leaks. The probe now uses a real
`apply_gate=False` bypass that returns the true ungated Qdrant ranking.

**Fix 2 — RELATIVE 0.93 -> 0.97:**
Measured leaks at 0.93:
- `ar` التجوال الدولي -> kept `faq/billing-cycle` @ ratio 0.965 (billing cycle, for a roaming question)
- `en` "why data slow" -> kept 3 irrelevant docs @ ratios 0.944-0.964

Noise ratios sat at 0.944-0.965; a 0.93 cutoff was never going to catch them. 0.97 drops every
measured leak while keeping all true positives on the 5-document calibration corpus.

**Fix 3 — Language asymmetry documented:**
Cross-lingual similarity is systematically lower than same-language (structural to e5-small, not
a tuning artifact). Headroom above the 0.7880 noise ceiling:

| Language | True positive | Headroom over noise ceiling |
|----------|--------------|---------------------------|
| English  | 0.8953       | +0.107                    |
| French   | 0.8606       | +0.073                    |
| Arabic   | 0.8310       | +0.043                    |

One global FLOOR is ~2.5x tighter for Arabic. This is now documented in the code, `.env.example`,
and the probe prints per-language margins so the engineer sees it coming.

### 1.3 Patch Application

The patch was created as `rag_phase6c_gate_retune.patch`. `git apply --3way` failed because the
working tree had uncommitted changes from prior phases (the git index did not match the patch
baseline). The exact same changes were applied manually via the edit tool, producing an
identical result. The diff was verified with `git diff` — every hunk matches the patch.

### 1.4 Build & Deploy

```
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --build knowledge-service
docker compose -f infra/docker-compose/docker-compose.yml -f infra/docker-compose/docker-compose.apps.yml up -d --force-recreate --no-build knowledge-service
```

Container recreated with the new image. Env vars verified inside the container:
```
RELATIVE_CUTOFF=0.97
SCORE_FLOOR=0.80
```

---

## 2. Patch Verification — Everything Set Up Perfectly

### 2.1 Code Changes Verified

**`retriever.py`** — all 4 hunks confirmed:
- Line 61-62: `DEFAULT_SCORE_FLOOR = 0.80`, `DEFAULT_RELATIVE_CUTOFF = 0.97` (was 0.93)
- Line 104: `apply_gate: bool = True` on `LexicalRetriever.search` signature
- Line 194: `apply_gate: bool = True` on `QdrantE5Retriever.search` signature
- Lines 220-226: ungated bypass block — `if not apply_gate: return passages` before `apply_relevance_gate`
- Lines 40-60: calibration comments with measured data table and language asymmetry documentation

**`knowledge_score_probe.py`** — full rewrite confirmed:
- `apply_gate=False` in `retriever.search()` call (was `min_score=0.0`)
- `top_k=10` (was 5)
- Per-language `(lang, query)` tuples with `tops: dict[str, float]` tracking
- Noise ceiling analysis: `ceiling = tops.get("control")`
- Per-language margin output: headroom over noise + margin over FLOOR
- Final warning line about raising the model, not the threshold

**`.env.example`** — confirmed:
- `KNOWLEDGE_RELATIVE_CUTOFF=0.97` (was 0.93)
- Calibration comments with language asymmetry note

**`.env`** (real) — confirmed:
- `KNOWLEDGE_RELATIVE_CUTOFF=0.97`

### 2.2 Health Check

```json
{
  "status": "ok",
  "model": "intfloat/multilingual-e5-small",
  "dimensions": 384,
  "collection": "telecom_knowledge",
  "points": 257,
  "checks": {
    "embedder": "ok",
    "qdrant_collection": "ok",
    "retriever": "ok"
  }
}
```

All 3 checks pass. 257 points (16 active documents).

### 2.3 Container Env Vars

```
RELATIVE_CUTOFF=0.97
SCORE_FLOOR=0.80
```

Both correctly loaded from `.env` into the container.

---

## 3. Verification Results on Real Corpus (16 documents, 257 chunks)

### 3.1 Arabic Leak Verification Query

**Command:**
```bash
curl -sS -H Content-Type:application/json -d '{"query":"كيف أفعل التجوال الدولي","top_k":5}' localhost:8102/search
```

**Patch expectation (5-doc corpus):** ONE passage (roaming-activation only, billing-cycle dropped).

**Actual result (16-doc corpus):** 5 passages returned.

| # | Score | Ratio | Source | Relevant? |
|---|-------|-------|--------|-----------|
| 1 | 0.8310 | 1.000 | procedures/roaming-activation.md | YES — correct answer |
| 2 | 0.8263 | 0.994 | faq/voice-call-problems.pdf | NOISE — voice calls, not roaming activation |
| 3 | 0.8237 | 0.991 | contracts/terms-fup-international-roaming.pdf | YES — roaming terms |
| 4 | 0.8158 | 0.982 | offers/value-added-services.pdf | NOISE — VAS, not roaming activation |
| 5 | 0.8141 | 0.980 | contracts/terms-fup-international-roaming.pdf | YES — roaming terms (different chunk) |

**Why this differs from the patch's 5-doc expectation:** The patch was calibrated on 5 documents
where each covered a distinct topic. With 16 documents (257 chunks), several documents now cover
roaming-related topics (terms-fup-international-roaming, voice-call-problems, value-added-services),
and E5 compresses their scores into a narrower band. The 0.97 relative cutoff keeps 5 passages
because their ratios are all above 0.97. This is exactly what the patch's "honest bottom line"
predicted: *"0.97 is right for a corpus where each document covers a distinct topic and only one
can be relevant. On a real corpus, several chunks of the same document will legitimately be
relevant and score close together — 0.97 will likely need to relax."*

### 3.2 Control Query (Hallucination Guard)

**Command:**
```bash
curl -sS -H Content-Type:application/json -d '{"query":"how do I fix my washing machine","top_k":5}' localhost:8102/search
```

**Expected:** `[]` (no passages — the corpus has no answer for a washing machine question).

**Actual result (16-doc corpus):** 5 passages returned.

| # | Score | Ratio | Source |
|---|-------|-------|--------|
| 1 | 0.8411 | 1.000 | faq/wifi-problems.pdf |
| 2 | 0.8315 | 0.989 | procedures/fixed-internet-router-diagnostics.pdf |
| 3 | 0.8294 | 0.986 | faq/wifi-problems.pdf |
| 4 | 0.8293 | 0.986 | faq/wifi-problems.pdf |
| 5 | 0.8249 | 0.981 | procedures/fixed-internet-router-diagnostics.pdf |

**CRITICAL FINDING:** The control query (non-telecom) returns 5 telecom passages. The noise
ceiling has risen from 0.7880 (5-doc corpus) to 0.8411 (16-doc corpus) — above FLOOR=0.80 and
above the Arabic true positive (0.8310). The relevance gate's FLOOR is no longer effective on
the real corpus. The gate threshold is `max(0.80, 0.8411 * 0.97) = 0.8159`, and all 5 control
passages score above it.

### 3.3 Full Probe Output (Ungated Distribution + Per-Language Margins)

**Command:**
```bash
docker compose run --rm knowledge-service python /app/scripts/knowledge_score_probe.py
```

**Output:**
```
gate: FLOOR=0.8  RELATIVE=0.97
scores below are UNGATED (apply_gate=False) - the real ranking

[en] how do I activate roaming abroad
   KEEP  0.8953  ratio=1.000  procedures/roaming-activation.md
   KEEP  0.8881  ratio=0.992  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8832  ratio=0.986  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8790  ratio=0.982  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8778  ratio=0.980  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8762  ratio=0.979  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8755  ratio=0.978  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8692  ratio=0.971  contracts/terms-fup-international-roaming.pdf
   drop  0.8667  ratio=0.968  contracts/terms-fup-international-roaming.pdf
   drop  0.8643  ratio=0.965  contracts/terms-fup-international-roaming.pdf

[fr] comment activer le roaming a l etranger
   KEEP  0.8606  ratio=1.000  procedures/roaming-activation.md
   KEEP  0.8367  ratio=0.972  faq/mobile-network-sim-troubleshooting.pdf
   drop  0.8343  ratio=0.969  contracts/terms-fup-international-roaming.pdf
   drop  0.8340  ratio=0.969  contracts/terms-fup-international-roaming.pdf
   drop  0.8283  ratio=0.962  contracts/terms-fup-international-roaming.pdf
   drop  0.8277  ratio=0.962  contracts/terms-fup-international-roaming.pdf
   drop  0.8246  ratio=0.958  contracts/terms-fup-international-roaming.pdf
   drop  0.8240  ratio=0.957  billing/billing-invoicing-account-management.pdf
   drop  0.8236  ratio=0.957  offers/offers-and-plans-catalog.pdf
   drop  0.8232  ratio=0.957  contracts/terms-fup-international-roaming.pdf

[ar] كيف أفعل التجوال الدولي
   KEEP  0.8310  ratio=1.000  procedures/roaming-activation.md
   KEEP  0.8263  ratio=0.994  faq/voice-call-problems.pdf
   KEEP  0.8237  ratio=0.991  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8158  ratio=0.982  offers/value-added-services.pdf
   KEEP  0.8141  ratio=0.980  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8096  ratio=0.974  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8094  ratio=0.974  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8088  ratio=0.973  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8074  ratio=0.972  contracts/terms-fup-international-roaming.pdf
   KEEP  0.8071  ratio=0.971  offers/value-added-services.pdf

[en] why is my mobile data slow
   KEEP  0.8869  ratio=1.000  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8755  ratio=0.987  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8755  ratio=0.987  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8740  ratio=0.985  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8722  ratio=0.983  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8692  ratio=0.980  faq/mobile-network-sim-troubleshooting.pdf
   KEEP  0.8679  ratio=0.979  faq/mobile-internet-troubleshooting.pdf
   KEEP  0.8679  ratio=0.979  faq/mobile-network-sim-troubleshooting.pdf
   KEEP  0.8670  ratio=0.978  faq/data-troubleshooting.md
   KEEP  0.8660  ratio=0.976  faq/mobile-network-sim-troubleshooting.pdf

[en] what is included in the Flexi plan
   KEEP  0.8732  ratio=1.000  offers/offers-and-plans-catalog.pdf
   KEEP  0.8727  ratio=0.999  offers/offers-and-plans-catalog.pdf
   KEEP  0.8615  ratio=0.987  offers/offers-and-plans-catalog.pdf
   KEEP  0.8614  ratio=0.986  offers/forfait-flexi.md
   KEEP  0.8570  ratio=0.981  offers/offers-and-plans-catalog.pdf
   KEEP  0.8562  ratio=0.981  offers/offers-and-plans-catalog.pdf
   KEEP  0.8550  ratio=0.979  offers/offers-and-plans-catalog.pdf
   KEEP  0.8505  ratio=0.974  offers/offers-and-plans-catalog.pdf
   KEEP  0.8488  ratio=0.972  offers/offers-and-plans-catalog.pdf
   KEEP  0.8483  ratio=0.971  offers/offers-and-plans-catalog.pdf

[control] how do I fix my washing machine
   KEEP  0.8411  ratio=1.000  faq/wifi-problems.pdf
   KEEP  0.8315  ratio=0.989  procedures/fixed-internet-router-diagnostics.pdf
   KEEP  0.8294  ratio=0.986  faq/wifi-problems.pdf
   KEEP  0.8293  ratio=0.986  faq/wifi-problems.pdf
   KEEP  0.8249  ratio=0.981  procedures/fixed-internet-router-diagnostics.pdf
   KEEP  0.8248  ratio=0.981  faq/wifi-problems.pdf
   KEEP  0.8225  ratio=0.978  procedures/fixed-internet-router-diagnostics.pdf
   KEEP  0.8222  ratio=0.978  faq/wifi-problems.pdf
   KEEP  0.8217  ratio=0.977  faq/mobile-network-sim-troubleshooting.pdf
   KEEP  0.8215  ratio=0.977  faq/mobile-network-sim-troubleshooting.pdf

noise ceiling (control top) = 0.8411
FLOOR margin over noise     = -0.0411   (want clearly positive)
  [en] top=0.8953  headroom over noise=+0.0542  margin over FLOOR=+0.0953
  [fr] top=0.8606  headroom over noise=+0.0195  margin over FLOOR=+0.0606
  [ar] top=0.8310  headroom over noise=-0.0101  margin over FLOOR=+0.0310

If a per-language 'margin over FLOOR' is near zero, real answers in that language are about to be dropped: raise the model, not the threshold.
```

### 3.4 Analysis — What the Real-Corpus Probe Data Shows

The patch was calibrated on a 5-document corpus. The real corpus now has 16 active documents
(257 chunks). The probe reveals three structural changes:

**Finding 1 — Noise ceiling rose from 0.7880 to 0.8411 (+0.053).**
With 16 telecom documents, E5 finds telecom-shaped content in everything — even a washing machine
query scores 0.8411 against wifi-problems.pdf. FLOOR=0.80 is now 0.0411 BELOW the noise ceiling.
The absolute gate is completely ineffective: the control query returns 10 passages, all flagged KEEP.

**Finding 2 — FLOOR margin over noise is NEGATIVE (-0.0411).**
The probe explicitly flags this: `(want clearly positive)`. On the 5-doc corpus the margin was
+0.012 (razor-thin but positive). On the 16-doc corpus it is -0.0411. The gate cannot distinguish
"no answer" from "has answer" anymore.

**Finding 3 — Arabic headroom over noise is NEGATIVE (-0.0101).**
The Arabic true positive (0.8310) scores BELOW the control query's noise (0.8411). This means a
non-telecom question in English outscored a real telecom question in Arabic. This is the
structural limit the patch warned about, now confirmed with evidence. The probe's final line
applies: *"If a per-language 'margin over FLOOR' is near zero, real answers in that language are
about to be dropped: raise the model, not the threshold."*

**Comparison: 5-doc calibration vs 16-doc real corpus:**

| Metric | 5-doc corpus | 16-doc corpus | Delta |
|--------|-------------|--------------|-------|
| Noise ceiling (control top) | 0.7880 | 0.8411 | +0.053 |
| FLOOR margin over noise | +0.012 | -0.0411 | -0.053 |
| EN true positive | 0.8953 | 0.8953 | 0 |
| EN headroom over noise | +0.107 | +0.054 | -0.053 |
| FR true positive | 0.8606 | 0.8606 | 0 |
| FR headroom over noise | +0.073 | +0.020 | -0.053 |
| AR true positive | 0.8310 | 0.8310 | 0 |
| AR headroom over noise | +0.043 | -0.010 | -0.053 |
| AR margin over FLOOR | +0.031 | +0.031 | 0 |
| Control passages returned | 0 (all dropped) | 10 (all KEEP) | +10 |

The true-positive scores are identical (same roaming-activation.md document), but the noise
ceiling rose uniformly by ~0.053. Every language lost exactly that much headroom. Arabic crossed
zero — its true positive is now below the noise.

**What this means for the engineer:**
The gate as currently tuned (FLOOR=0.80, RELATIVE=0.97) is broken on the real corpus. The
control query returns 5 passages through the live `/search` endpoint. The patch's prediction was
exact: *"The pipeline is finished; the calibration isn't, and it can't be until there are real
documents in it."* The calibration data is now available. The next step is to raise FLOOR above
the new noise ceiling (0.8411 — suggest FLOOR=0.85 minimum) and/or move to a cross-encoder
reranker that can separate relevant from irrelevant at the top of the ranking, which thresholds
alone cannot do at this corpus size.

---

## 4. Uploaded Knowledge Files (13 PDFs)

The following 13 PDF files were uploaded via `POST /knowledge/upload` and ingested into the
knowledge base. All 13 are active (`status=ready`) and indexed in Qdrant.

| # | Source (MinIO key) | Title | Type | Language | Chunks |
|---|---------------------|-------|------|----------|--------|
| 1 | billing/billing-invoicing-account-management.pdf | billing invoicing account management | billing | fr | 23 |
| 2 | contracts/terms-fup-international-roaming.pdf | terms fup international roaming | contracts | fr | 22 |
| 3 | faq/device-compatibility.pdf | device compatibility | faq | fr | 14 |
| 4 | faq/mobile-internet-troubleshooting.pdf | mobile internet troubleshooting | faq | fr | 16 |
| 5 | faq/mobile-network-sim-troubleshooting.pdf | mobile network sim troubleshooting | faq | fr | 23 |
| 6 | faq/sms-messaging-issues.pdf | sms messaging issues | faq | fr | 16 |
| 7 | faq/voice-call-problems.pdf | voice call problems | faq | fr | 17 |
| 8 | faq/wifi-problems.pdf | wifi problems | faq | fr | 16 |
| 9 | offers/mobile-offers-plans-hardware.pdf | mobile offers plans hardware | offers | fr | 22 |
| 10 | offers/offers-and-plans-catalog.pdf | offers and plans catalog | offers | fr | 29 |
| 11 | offers/value-added-services.pdf | value added services | offers | fr | 16 |
| 12 | procedures/fixed-internet-router-diagnostics.pdf | fixed internet router diagnostics | procedures | fr | 23 |
| 13 | procedures/number-portability.pdf | number portability | procedures | fr | 15 |

**Total PDF chunks: 252.** Combined with 5 original MD documents (5 chunks), the corpus has 257
chunks across 18 active documents (1 archived test file excluded).

### Original Built-in MD Documents (5)

| Source | Title | Type | Chunks |
|--------|-------|------|--------|
| faq/billing-cycle.md | Invoice and billing cycle | faq | 1 |
| faq/data-troubleshooting.md | Mobile data is not working | faq | 1 |
| offers/forfait-flexi.md | Forfait Flexi postpaid plan | offers | 1 |
| procedures/plan-change.md | Change your mobile plan | procedures | 1 |
| procedures/roaming-activation.md | Activate international roaming | procedures | 1 |

### Archived Document (1)

| Source | Status | Note |
|--------|--------|------|
| tests/env_config.txt | archived | Purged in Phase 6a (junk file, 12 chunks) |

---

## 5. Important Note: Mock/Seed Data Is NOT Used by the RAG Service

**Nothing from the mock seed data (reference.products, reference.recharge_catalog,
seed_reference.py, seed_pilot.py) will be used in future works beside the RAG service we have,
or even as a fallback.**

The RAG knowledge service is the single source of truth for offer descriptions, procedures, and
FAQs. The mock seeds are development-only fixtures that no production code reads at runtime. They
can be abandoned without risk. Details below.

---

## 6. Rapport d'etat : Offres telecom et seeds dans le systeme

### 6.1 Les 3 offres mock (seed data)

Definies dans `packages/persistence/seed/seed_reference.py:30-31` et inserees dans la table
`reference.products` :

| Code produit | Nom affiche | Type |
|-------------|------------|------|
| FLEXI | Postpaid Flexi | POSTPAID |
| TRANKIL | Prepaid Mobile | PREPAID |
| FIBER | Fibre Fixe | POSTPAID |

Egalement, 4 recharges prepayees dans `reference.recharge_catalog` : R5 (5 TND), R10 (10 TND + 1
bonus), R20 (20 TND + 3 bonus), R50 (50 TND + 10 bonus).

### 6.2 Statut dans le code applicatif — aucune dependance dure

- **Aucun code ne requete `reference.products` ou `reference.recharge_catalog` au runtime** — ni
  dans les services, ni dans l'API, ni dans les agents.
- `crm.subscriptions.plan_code` est une simple `String(50)` sans contrainte de cle etrangere vers
  `reference.products`.
- Le `change_plan` tool (`account_tools.py:46`) accepte n'importe quel string — aucune validation
  contre la base.
- Les lecteurs (context-service, business-api) ont un fallback : `subscription.plan_code or
  subscription.plan_type`.
- Les seuls fichiers qui referencent `Product` et `RechargeCatalog` sont :
  - `seed_reference.py` (insertion)
  - `0006_reference.py` (migration)
  - `models/reference.py` (definition ORM)

**Ce qui reste vrai apres suppression des seeds :**
- Les abonnements des clients pilotes continuent d'afficher "Postpaid Flexi", "Prepaid Mobile",
  "Fibre Fixe" — car ce sont des chaines stockees dans `crm.subscriptions.plan_code`, pas des
  valeurs lues depuis `reference.products`.
- Le RAG (corpus + PDFs) est deja independant et fait autorite pour les descriptions d'offres.
- Le `change_plan` tool accepte n'importe quel string — il ne valide rien contre la base.
- Rien n'est "weird" dans l'etat actuel. Le systeme est deja concu pour fonctionner sans ces
  seeds. Si vous voulez nettoyer, il suffit de ne plus executer `seed_reference.py` /
  `seed_pilot.py` en prod, et eventuellement de retirer ces fichiers ou de les marquer comme
  deprecies. Le modele `Product` et la table `reference.products` peuvent rester (utiles si un
  jour vous voulez un vrai catalogue porte par une UI admin), ou etre supprimes proprement.

### 6.3 Clients pilotes — 3 abonnes mock dans seed_pilot.py

| Client | MSISDN | plan_code (stocke dans la DB) | Type |
|--------|--------|-------------------------------|------|
| Amine Ben Salah | +21620155320 | "Postpaid Flexi" | POSTPAID |
| Yousra Trabelsi | +21629744108 | "Prepaid Mobile" | PREPAID |
| Karim Gharbi | +21652310977 | "Fibre Fixe" | POSTPAID |

**Note :** `seed_pilot.py` utilise les noms des produits comme `plan_code`, pas les codes
(FLEXI, etc.). Ces valeurs sont deja ecrites en base et ne dependent pas des seeds — les
supprimer ne les efface pas des abonnements existants.

### 6.4 Etat du RAG — offre documentee dans le corpus

`corpus.py:22-33` — un seul document d'offre :

> Forfait Flexi : 25 TND/mois, 20 Go data, appels illimites TT, 120 min autres reseaux, *111#

**Manquant dans le RAG (non documentes nulle part dans le corpus) :**
- Prepaid Mobile (TRANKIL) — paliers de recharge, bonus, duree de validite
- Fibre Fixe (FIBER) — debit, prix, engagement

**PDFs existants dans `RAG knwoledge docs/` (13 fichiers) :**
- `offers and plans catalog.pdf` — catalogue d'offres (uploaded, 29 chunks)
- `mobile offers plans hardware.pdf` — offres mobiles (uploaded, 22 chunks)
- 11 autres PDFs (facturation, roaming, depannage, etc.) — tous uploaded et ingeres

Ces PDFs sont deja deposes dans MinIO et ingeres via `/knowledge/upload` — ils sont disponibles
dans la recherche vectorielle.

### 6.5 Flux de bout en bout actuel

```
seed_reference.py -> reference.products (table, jamais lue)
                        |
seed_pilot.py -> crm.subscriptions.plan_code = "Postpaid Flexi" (string stocke)
                        |
context-service -> Customer360.subscription_type = "Postpaid Flexi" (fallback si null)
agent-worker -> get_plan_details() -> affiche subscription_type
                        |
LLM decide quoi proposer / le RAG retourne le detail de l'offre depuis corpus.py / Qdrant
```

### 6.6 Questions en suspens pour la suite

1. **Suppression des tables ?** Les tables `reference.products` et `reference.recharge_catalog`
   existent mais ne sont jamais lues. On peut soit les garder (vides, inoffensives), soit les
   supprimer via migration.

2. **Clients pilotes ?** `seed_pilot.py` garde 3 abonnes mock utiles pour le developpement local
   et les tests. Leurs `plan_code` sont juste des chaines statiques en base — pas liees aux
   seeds.

3. **Enrichissement RAG ?** Les descriptions detaillees de Prepaid Mobile et Fibre Fixe sont
   absentes du corpus. À ajouter soit dans `corpus.py` (versionne, seed automatique via
   `seed_knowledge_bucket.py`), soit dans des PDFs/Markdown dans le bucket MinIO.

---

## 7. Where the RAG Pipeline Stands

All seven phases are done and verified on real runs:

1. **Phase 3** — Schema, embeddings, ingestion pipeline
2. **Phase 4** — Dense retrieval (QdrantE5Retriever, no silent fallback)
3. **Phase 5a** — Multi-format ingestion + upload API
4. **Phase 5b** — Metadata filters + reindex recovery
5. **Phase 6a** — Corpus lifecycle (list + purge)
6. **Phase 6b** — Relevance gate (FLOOR + RELATIVE) + silent-agent bug fix
7. **Phase 6c** — Evidence-based gate retune (probe bug fix, 0.93 -> 0.97, language asymmetry)

Cross-lingual FR/AR -> EN retrieval works, the corpus is curatable, the index is rebuildable,
and a knowledge failure can no longer silence a caller.

**The honest bottom line:** Every threshold here was fitted to 5 documents. On the real 16-doc
corpus, the probe data shows the noise ceiling has risen above FLOOR, and the Arabic true
positive has fallen below the noise. The gate needs full recalibration on the real corpus —
raise FLOOR above 0.8411, and/or move to a cross-encoder reranker. The pipeline is finished; the
calibration isn't, and now it can be because the probe data is available. This is the concrete
trigger for the reranker that was deferred: when an Arabic true positive approaches FLOOR, raise
the model (e5-base, or jina-reranker-v2-multilingual at 1.11 GB), don't nudge the threshold. That
is now an evidence-based decision instead of a guess.

---

## 8. Next Steps

1. **Raise FLOOR above the new noise ceiling (0.8411).** Suggest FLOOR=0.85 as a starting point.
   Re-run the probe to verify the control query returns `[]`.
2. **Relax RELATIVE from 0.97.** On the real corpus, legitimate same-topic chunks score within
   97% of each other. 0.97 keeps too many passages. Re-calibrate from the probe data.
3. **Add a cross-encoder reranker** (jina-reranker-v2-multilingual, 1.11 GB) to separate relevant
   from irrelevant at the top of the ranking, which thresholds alone cannot do at this corpus
   size.
4. **Watch Arabic false negatives.** The Arabic true positive (0.8310) is below the noise
   ceiling (0.8411). Any FLOOR above 0.8310 will drop real Arabic answers. This is the structural
   limit of e5-small — only a larger model or a reranker can fix it.
5. **Enrich the corpus** with Prepaid Mobile (TRANKIL) and Fibre Fixe (FIBER) descriptions, which
   are currently missing from both the RAG corpus and the PDFs.
6. **Decide on seed cleanup.** The mock seeds (`reference.products`, `reference.recharge_catalog`)
   are never read at runtime and can be removed or kept (inoffensive). See section 6.6 above.
