# P2-3 — Operational soundness

**Base:** `version_88`, code commit `186d406c`, HEAD `cc27a69b` (docs-only: `version_88: add version documentation`). Every verbatim block below is current at both.

**Why this cookbook exists:** the master roadmap order (P0-1 → P2-2) is now **exhausted**. Every item in §2 of the roadmap is applied and pushed. What remains is not feature work — it is the set of things that are *broken or unverified in the running system*, which is why this cookbook is scoped by operational impact rather than by roadmap number.

**Bundles:** J (restore `knowledge-service` — the only DOWN service) · K (CI truthfulness — closes P1-3's open facts) · L (the broken `.venv` that has been worked around in five consecutive patches) · M (`billing.accounts` seed gap that makes a shipped P2-1 feature look empty).

**No tests, no CI test authoring, no new test libraries.** Bundle K *repairs* the existing pipeline; it does not add suites. Verification is live and manual, expressed as invariants.

---

## §0 — Read this before you open an editor

### Two conventions CHANGED as a result of P2-2. These supersede the earlier wording.

**1. The session rule, corrected.** P2-2's Bundle G4 proved my earlier absolute phrasing wrong, and the implementer was right to override it. The rule is not "every mutation route uses `session_scope()`". The rule is:

> **A mutation and its audit entry must share ONE session.**
> - If the route **already** mutates through the injected `DbSession`, append on that same session and call `session.commit()` explicitly.
> - Use `session_scope()` **only when the route owns no session yet.**

The P2-1 close route owned no session, so `session_scope()` was correct there. The four `/auth/*` routes already wrote credentials through the injected `DbSession`, so converting them to `session_scope()` would have opened a *second* transaction — splitting the credential write from its audit entry — and would have bypassed the rolled-back fixture session in `tests/conftest.py`, breaking `test_auth_http.py`. Both the durability argument and the test argument point the same way. **My rule was too absolute; this is the corrected form.**

**2. Grep gates must exclude documentation paths.** P2-2's J4.3 and J4.5 both tripped on the cookbooks and version docs that *describe* the gate rather than on live config. This is the second time I have shipped a self-tripping gate. Every gate in this cookbook is scoped:

```bash
# WRONG — matches the cookbook that documents the gate
git grep -n "dev-key-123"

# RIGHT — only live config, source and infra
git grep -n "dev-key-123" -- apps/ services/ packages/ infra/ Frontend/ scripts/ Makefile
```

Exclude `features_to_apply/`, `docs/versions/`, `answers.md`, `correction_results.md`, `commands.md` and `services/*/[a-z]*_results.md`. Those are frozen historical snapshots and must not be rewritten to satisfy a gate.

### Conventions still in force

3. **Never hand-format imports.** Add the line, run `python -m ruff check --fix <path>`.
4. **Alembic `drop_constraint` takes the RAW constraint name.** No migration in P2-3, but the rule stands.
5. **Rule 1.4** — do not claim what a component or module does without opening it. A size from a directory listing is not a read. This extends to import graphs.
6. **Express expectations as invariants, never literals.** P2-2 saw `failed_rows` drift 33 → 34 between patches. Third confirmation.
7. **Never insert `audit.audit_ledger` rows from raw SQL.** Go through `PgAuditLedger`.
8. **Backend source change ⇒ rebuild. Env-only change ⇒ `docker compose up -d` (recreate).**
9. **Do not delete or modify existing backend logic or behaviour.** Bundle J changes *build and runtime configuration only* — not one line of `knowledge_service` source.

### Deliberately not in scope

- **R11** (`customer_360`'s `!= "paid"` blacklist) — closed by your decision.
- **R12** (GLPI revert, H-3) and **R14** (persona contract, 5 FAIL / 43 OK) — real, but neither blocks the dashboard or the running system. They belong in a later pass.
- **R15 lint debt** — the mypy `ignore_errors` ratchet across 14 modules and the ruff burn-down. Bundle K deliberately does **not** unwind the ratchet: doing so mid-pipeline-repair would make a green pipeline go red for reasons unrelated to the repair.
- **Making `sentence-transformers` an optional extra.** See §J4 for why I am not doing this, even though it would permanently kill H-6.

---

# BUNDLE J — Restore `knowledge-service` (H-6)

`make health` has reported **10/11 with only `knowledge-service:8102` DOWN** across P1-2, P1-3, P2-1 and P2-2. It has been carried as "pre-existing, out of scope" four times. It is now the single largest functional hole in the system: the agent's entire RAG path is dead, and `services/knowledge-service` is 15 modules and ~136 KB of working code that nothing can reach.

## J0 — H-6 is not one bug. It is two, and the second one is the reason health never recovers.

I had been recording H-6 as "torch==2.2.2 hash mismatch". Reading the service proves that is only the *build* failure. There is a second, independent cause of the DOWN state, and fixing torch alone will not clear it.

**Cause 1 — the build.** `services/knowledge-service/Dockerfile`:

```dockerfile
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

There is **no `--require-hashes` and no hash pinning anywhere in this file**, and `PIP_NO_CACHE_DIR=1` is set at `ENV` level *and* passed on the command line. So the reported mismatch (expected `431a747b5a…`, got `5421564bfe…`) cannot be a stale local cache and cannot be a hash you pinned. It is pip comparing the downloaded artifact against the hash the PyTorch CPU index declared for it — a mismatch there means **the bytes that arrived are not the bytes the index advertised.** On a ~118 MB wheel that is a truncated or corrupted transfer, or a CDN serving a re-cut artifact.

**Cause 2 — the infra tier is down, and `/health` fails closed by design.** The P2-2 results §0 record `redis/minio/qdrant/otel in Exited (255)`, pre-dating that patch. `services/knowledge-service/problems_solving_steps.md` RED FLAG 3 documents that the retriever factory was *deliberately* rewritten to:

> - Raise `RetrieverUnavailable` when the collection or embedder is unusable
> - Never return `LexicalRetriever` unless `KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true` is explicitly set
> - Return 503 on `/search` and `/health` when the retriever is unavailable

and that `/health` reports exactly three checks: `embedder`, `qdrant_collection`, `retriever`. **With Qdrant in `Exited (255)`, `qdrant_collection` cannot pass, so `/health` returns 503 and `make health` reports DOWN — even from a perfectly built image.** That fail-closed behaviour is a feature, not a defect: it is the fix for RED FLAG 3's silent lexical downgrade. Do not touch it.

> **Consequence for sequencing:** repair the infra tier and the collection *first*, then the build. If you rebuild the image first you will still see DOWN and will wrongly conclude the torch fix failed.

## J1 — Bring the infra tier up and confirm which of the two causes you actually have

Infra is a separate compose file from the app tier. From the repo root:

```bash
docker compose -f infra/docker-compose/docker-compose.yml up -d
docker compose -f infra/docker-compose/docker-compose.yml ps
```

All of postgres, redis, qdrant, minio and the otel collector must be `Up`. `Exited (255)` on restart usually means a port conflict or a corrupt volume — read the container's logs before doing anything destructive, and **never delete a volume** (H-2 extends to Qdrant and MinIO: MinIO holds the ingested source documents and Qdrant holds the only copy of the vectors).

Then establish which failure you are actually looking at:

```bash
# Does an image even exist? If this is empty, Cause 1 is real and the build never succeeded.
docker images | grep knowledge

# If an image exists, the build was fine and you have Cause 2 only.
curl.exe -s localhost:8102/health
```

`docker images` showing no `knowledge-service` ⇒ do J2. An image present but `/health` 503 ⇒ skip to J3.

## J2 — Make the torch wheel download survive a flaky transfer

The build is one `RUN` with no retry budget, so a single truncated read of a 118 MB wheel fails the whole image. Reproduce it first and capture the real pip error rather than trusting my summary of it:

```bash
docker build -f services/knowledge-service/Dockerfile -t knowledge-service . 2>&1 | tee /tmp/ks-build.log
grep -n -i -A5 "hash\|THESE PACKAGES DO NOT MATCH\|ERROR" /tmp/ks-build.log | head -60
```

Then apply the minimal fix. In `services/knowledge-service/Dockerfile`, replace:

```dockerfile
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

with:

```dockerfile
# H-6: a single truncated read of the ~118 MB CPU wheel failed the whole image with a hash
# mismatch against the index-declared hash. Give the transfer a retry budget and a longer
# timeout; the version, the index and the CPU-before-sentence-transformers ordering are unchanged.
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
      torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu \
 && python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
```

Three properties, all deliberate:

- **The pin, the index and the ordering are untouched.** `torch==2.2.2` from the CPU index installed *before* `sentence-transformers` is what keeps pip from resolving the ~2 GB CUDA stack, and the `numpy>=1.26,<2` ABI note downstream depends on this exact torch build. Changing the version would invalidate both.
- **`--retries 10 --timeout 120`** is the whole fix for a transport-level failure. Nothing else in the file needs to change.
- **The `python -c` verification makes the layer self-proving.** It must print `cuda False` — if it ever prints `cuda True`, pip resolved the CUDA wheel and the image is about to be ~2 GB heavier for nothing.

> **If the retry budget does not fix it**, the wheel genuinely is not retrievable and you have an upstream availability problem, not a build bug. Do **not** start bumping versions to make the build pass — `2.2.2` is load-bearing for the numpy 1.x ABI. Use J4 instead and record it as a deliberate degradation.

## J3 — The collection and the outbox: why a healthy image can still report 503

A fresh container against a Qdrant that has just come back up has **no collection**, and `qdrant_collection` will fail. `problems_solving_steps.md` RED FLAG 1 and RED FLAG 2 document this exact trap and its resolution, and the two console scripts already exist in `pyproject.toml` (`knowledge-bootstrap-qdrant`, `knowledge-sync-outbox`). Run them in this order:

```bash
# 1. Create the collection at the right dimension/distance (384 / cosine). Idempotent.
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml \
  run --rm knowledge-service knowledge-bootstrap-qdrant

# 2. Confirm it exists. points_count 0 is EXPECTED at this stage.
curl.exe -s localhost:6333/collections/telecom_knowledge

# 3. Drain the outbox into Qdrant. Re-embeds from knowledge.chunks.text_content.
docker compose -f infra/docker-compose/docker-compose.yml \
  -f infra/docker-compose/docker-compose.apps.yml \
  run --rm knowledge-service knowledge-sync-outbox
```

**Do not reach for `knowledge-ingest` to repopulate.** RED FLAG 2 is precisely that trap: ingestion is checksum-idempotent, so if the source bytes in MinIO are unchanged it reports `INGESTED=0 UNCHANGED=n`, re-embeds nothing, and never re-creates the outbox events. The outbox drain is the correct path.

Invariants, not counts:

```sql
-- every outbox event must be terminal-successful; anything in failed is a real problem
SELECT status, count(*) FROM knowledge.sync_outbox GROUP BY 1;
```

- `knowledge.sync_outbox` has **zero rows in `failed`** and zero left `pending`.
- `points_count` in Qdrant is **strictly greater than 0** and equals the number of active chunks. Do not assert `5` — that figure is from the Phase-3 corpus and the corpus has changed since.
- A `dimension mismatch` error from the drain means the embedding model changed since ingestion. The worker refuses the write on purpose (`len(vector) == chunk.embedding_dimensions`). The remedy is a re-ingest, not a force.

## J4 — The CE gate is an env kill-switch, and that is the documented degradation

This is the finding that makes Bundle J safe to attempt: **torch is not on the readiness path at all.**

`ce_gate.py` imports both `sentence_transformers` and `torch` **lazily, inside `_ensure_model`**, each wrapped:

```python
                try:
                    from sentence_transformers import CrossEncoder
                except Exception as exc:
                    raise CEGateError(f"sentence-transformers import failed: {exc}") from exc
                try:
                    import torch
                    torch.set_num_threads(int(os.getenv("KNOWLEDGE_CE_THREADS", "4")))
                except Exception:
                    pass
```

`CEGateError` is documented as *"Surfaced so the caller can degrade gracefully"*, `get_ce_gate()` is built lazily "so a cold start does not block the container", the Dockerfile states the CE model "loads at runtime (lazy, outside readiness); failure degrades gracefully (no 503)", and `/health`'s three checks are `embedder`, `qdrant_collection`, `retriever` — **the CE gate is not among them.** Four independent sources agree.

So if and only if J2's retry budget cannot retrieve the wheel, disable the gate by configuration — **zero code change**:

```
KNOWLEDGE_CE_GATE_ENABLED=false
```

`ce_gate_enabled()` reads exactly this, defaulting to `"true"`:

```python
def ce_gate_enabled() -> bool:
    return os.getenv("KNOWLEDGE_CE_GATE_ENABLED", "true").strip().lower() == "true"
```

Env-only, so `docker compose up -d` (recreate), not a rebuild.

**State the cost honestly when you do this.** The gate exists to solve a real retrieval defect, documented in its own module docstring: on a same-language French corpus, dense cosine inflates noise (recruitment `0.86`) above real answers (roaming-signal `0.85`), so no threshold separates them. Disabling the gate reinstates that inversion. Retrieval still works and `/health` still reports `ok`; precision on French-only queries gets worse. That is a degradation to be recorded in the results file, not a fix.

**Two things I am deliberately NOT prescribing:**

- **`KNOWLEDGE_ALLOW_LEXICAL_FALLBACK=true` — never set this.** RED FLAG 3 is the story of exactly that silent downgrade: the agent answered from term-overlap over an in-memory corpus while appearing to be RAG-backed. The flag exists so the fallback can never happen by accident. Setting it to make health go green would be re-introducing the original defect and lying about it.
- **Moving `sentence-transformers==3.3.1` to an optional extra in `pyproject.toml`.** It would permanently remove torch from the build and end H-6 forever. I am not prescribing it because `reranker.py` (6,251 B) is a second consumer I have not opened, so I cannot state what else breaks, and because it converts a transient transport failure into a permanent capability loss. If you want it, read `reranker.py` and `embeddings.py` first and treat it as its own bundle with its own decision.

## J5 — Proof that the service is genuinely restored

`make health` reporting 11/11 is necessary but not sufficient — it only proves `/health` returned 200. Prove retrieval actually works, using the cross-lingual test the service's own docs define as definitive:

```python
from knowledge_service.retriever import get_retriever
for q in ['how do I activate roaming abroad',
          'comment activer le roaming a l etranger',
          'كيف أفعل التجوال الدولي']:
    print(q)
    for p in get_retriever().search(q, top_k=2):
        print(f'   {p.score:.3f}  {p.source}  [{p.language}/{p.document_type} v{p.version}]')
```

Invariants:

- `/health` returns 200 with `embedder: ok`, `qdrant_collection: ok`, `retriever: ok` — **all three**, not just a 200.
- All three languages surface the **same** top document, proving the aligned multilingual E5 vector space is live and that this is real dense retrieval rather than a lexical fallback. The docs expect `procedures/roaming-activation.md` with scores > 0.8; assert on *agreement across the three languages* rather than on that filename, since the corpus may have moved on.
- The Arabic query returning a result at all is the strongest single signal — a lexical fallback cannot match Arabic against a French corpus.
- If you disabled the CE gate in J4, say so next to these numbers.

> **`make health` is 10/11 for a second reason if you skip J1.** Once knowledge-service is genuinely up, 11/11 is the expected state. If it stays 10/11 with a *different* service down, that is new and unrelated — report it, do not absorb it.

---

# BUNDLE K — CI truthfulness (closes P1-3's open facts)

P1-3 shipped the pipeline and has been carried as **"inspected and locally verified, not verified"** ever since, because no Actions run was ever read. Reading `.github/workflows/ci.yml` at v88 closes three of the four open questions from static evidence, and surfaces one real defect.

## K0 — Three of P1-3's four open facts, answered from the workflow itself

| Open question | Answer | Evidence |
|---|---|---|
| Did the push trigger fire on `version_*`? | **Yes** | `branches: [ main, 'version_*' ]` — P1-3's fix is live, so every `version_NN` push since has run CI |
| Which jobs ran? | **`lint`, `test`, `db-migrations` only** | `docker-build`, `docker-build-apps` and `security-scan` each carry `if: github.ref == 'refs/heads/main'` |
| Did `knowledge-service` build? | **No — and it never does on a version branch** | it appears only in the `docker-build` matrix, which is main-gated |

That last row matters for Bundle J: **the H-6 build failure has never been exercised by CI**, because the image is only built on `main`. The first merge to `main` will hit it. Fixing J before that merge is what keeps `main` green.

Only the **`test` job duration** still needs a run read. One command:

```bash
gh run list --branch version_88 --limit 5
gh run view <run-id>            # per-job conclusions and durations
```

Record the `test` job's duration verbatim in the results file. My prediction, and the reason for K1: **it is either very slow or it failed on disk.**

## K1 — The real defect: the `test` job pulls the ~2 GB CUDA torch stack

The `test` job installs the services from the default PyPI index:

```yaml
      - name: Install services, MCP servers and apps
        run: |
          pip install ./services/context-service ./services/knowledge-service ./services/decision-service \
```

`services/knowledge-service/pyproject.toml` depends on `sentence-transformers==3.3.1`, which depends on **torch**. With no index override, pip resolves torch from PyPI — the CUDA build, which drags in the `nvidia_*` wheels. The Dockerfile solves this explicitly and says so:

```dockerfile
# Install torch CPU-only BEFORE sentence-transformers so pip resolves the dep to the
# light (~118 MB) CPU wheel instead of pulling ~2 GB of CUDA libs.
RUN pip install --no-cache-dir torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

**CI does not replicate that step.** A GitHub-hosted runner has ~14 GB free on `/`, so this is at best minutes of wasted download on every push and at worst a disk-space failure. The fix is to mirror the Dockerfile's ordering — same version, same index, same rationale.

In `.github/workflows/ci.yml`, inside the `test` job, insert a step **before** `Install services, MCP servers and apps`:

```yaml
      # Mirrors services/knowledge-service/Dockerfile: install torch CPU-only FIRST so pip resolves
      # sentence-transformers' dependency to the light (~118 MB) CPU wheel instead of ~2 GB of CUDA
      # libs. Same pin as the image (2.2.2 is load-bearing for the numpy 1.x ABI).
      - name: Install torch (CPU-only) before service deps
        run: pip install --retries 10 --timeout 120 torch==2.2.2 --index-url https://download.pytorch.org/whl/cpu
```

Properties: same pin and index as the image, so CI and the container resolve the identical torch; `--retries/--timeout` carry J2's transport fix into CI; `cache: pip` is already set on this job's `setup-python`, so the wheel is cached across runs after the first.

> Do **not** "fix" this by dropping `./services/knowledge-service` from the install list. `run_tests.py` target 9 is `services/knowledge-service` with `tests` — removing the install would break that suite, which is exactly the CI/`make test` drift P1-3 existed to end.

## K2 — One thing I checked and it is NOT a bug

The `db-migrations` job does:

```yaml
          cd packages/persistence
          alembic upgrade head
          python -m seed.seed_pilot
          python -m seed.seed_reference
```

I expected `seed` to be unimportable, because `packages/persistence/src/` contains only `persistence`. It resolves correctly: **`packages/persistence/seed/` exists as a sibling of `src/`**, so with cwd at `packages/persistence` the `seed` package is on `sys.path`. Verified by listing, not assumed. No change needed.

Also correct by omission: the job runs `seed_pilot` and `seed_reference` but **not** `seed_auth_credentials`, which raises `RuntimeError: AUTH_CIN_HMAC_KEY must contain at least 32 characters` without that secret. Leaving it out is right.

And `run_tests.py`'s 17 targets are all covered by the `test` job's install list — the three sim services (`nms-sim`, `ocs-billing-sim`, `provisioning-sim`) are absent from both, consistently. No drift.

## K3 — The `lint` job needs a read before you trust it

```yaml
      - name: Install tooling
        run: pip install ruff mypy
      - name: Type check (mypy)
        run: mypy packages/ services/ apps/
```

mypy runs with **no project dependencies installed**, while P1-3's local "Success: no issues found in 236 source files" was measured with everything installed. Whether that still passes depends entirely on the mypy configuration in the root `pyproject.toml` — specifically `ignore_missing_imports`. **I have not read that file, so I am not asserting either outcome.** Read the `[tool.mypy]` block, then:

- If `ignore_missing_imports = true` (or per-module overrides cover the third parties), the job is fine as written — change nothing.
- If it is not set, the job has been failing or is one dependency away from failing, and the honest fix is to install the same package set the `test` job installs. Do not add `ignore_missing_imports` globally just to make it green; that silently weakens type checking repo-wide.

Either way, `gh run view` tells you the real answer in one call — do that before editing.

---

# BUNDLE L — The broken `.venv`

This has forced the same manual workaround in P1-2, P1-3, P2-1 and P2-2: `make migrate` fails with `No module named alembic.__main__`, so every patch has run `PYTHONPATH=packages/persistence/src python -m alembic upgrade head` by hand, and `make test` has never run end to end.

**It requires no repository change at all.** Two reads settle it.

`.gitignore` line 4:

```
.venv/
```

So `.venv` is **untracked** — a local artifact on your machine, not something the repo ships. My backlog wording ("the repo-shipped `.venv`") was wrong.

And the `Makefile` already has a four-step interpreter fallback:

```makefile
PYTHON := "$(shell if [ -x .venv/bin/python ]; then echo $(CURDIR)/.venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo $(CURDIR)/.venv/Scripts/python.exe; elif command -v python3 >/dev/null 2>&1; then echo python3; else echo python; fi)"
```

The defect is now exact: **`[ -x .venv/bin/python ]` is true for a broken launcher.** The test asks "is this file executable", not "does this interpreter work", so the first branch wins and the `python3` fallback never gets a chance. The Makefile logic is fine; the artifact it finds is poisoned.

**Immediate workaround nobody has used — no files touched, works right now:**

```bash
make PYTHON=python3 migrate
```

A command-line variable overrides a makefile `:=` assignment, so this bypasses the broken venv for any target.

**The actual repair — remove the poisoned artifact:**

```bash
# confirm it is the launcher that is broken, not python itself
./.venv/bin/python -V ; ./.venv/bin/python -c "import alembic"

rm -rf .venv                      # untracked; nothing in git changes
make PYTHON=python3 migrate       # fallback now resolves cleanly
```

Or recreate it properly for the current OS, which restores `make` with no arguments:

```bash
python3 -m venv .venv
make install                      # PIP/PYTHON now resolve to .venv, editable installs land there
```

**Invariant:** `make migrate` completes and reports alembic at head, and `make test` runs `scripts/run_tests.py` to completion — the first time in five patches. Note `SHELL := /bin/bash`, so these need WSL/Git Bash; the file's own header says PowerShell users run `.\start.ps1` instead.

> **Optional hardening, only if you want it.** The fallback could probe that the interpreter *works* rather than that the file is executable — `if .venv/bin/python -c "" 2>/dev/null; then`. That is a real improvement, but it edits a working build file to defend against a local artifact you are about to delete. My recommendation is to delete the artifact and leave the `Makefile` alone. **Makefile recipe lines require literal TABs** if you do edit it.

---

# BUNDLE M — `billing.accounts` = 2 rows is CORRECT. I was wrong.

I have carried this in the backlog as a defect: *"`billing.accounts` has only 2 rows — most customers have no account_number."* Reading `packages/persistence/seed/seed_pilot.py` proves that is **domain-correct seeding, not a gap**, and that the bundle I was about to write would have injected invalid data.

The seed creates exactly three customers:

| Customer | CIN | Plan | `billing.Account` | `ocs.BalanceAccount` | Invoice |
|---|---|---|---|---|---|
| Amine Ben Salah | `11224087` | POSTPAID / FLEXI | **`BA-000021`** | — | `INV-2026-04-100021` issued |
| Yousra Trabelsi | `33449912` | **PREPAID** / TRANKIL | **none** | main 7.300 TND + data 1840 MB | none |
| Karim Gharbi | `55662256` | POSTPAID / FIBER | **`BA-000078`** | — | `INV-2026-04-100078` overdue |

and prints `"seeded 3 customers, 3 subscriptions, 2 invoices, 2 balances"` — **2 invoices and 2 accounts are the stated, intended output.**

Yousra is prepaid. In this domain a prepaid line carries an OCS `BalanceAccount`, not a billing `Account`; a prepaid customer has no billing account number because there is nothing to bill. So `2 accounts / 3 customers` is right, and P2-1's live result — `/api/v1/me/profile/detail` returning `account_number: null` for Yousra, which the results file called "truthful" — is not just truthful, it is **permanently and correctly null**.

**Do not add accounts for prepaid customers.** That would fabricate a billing relationship that does not exist, corrupt `customer_360` and the ledger surfaces, and violate the CHECK-constrained plan model. This is the mistake this read prevented.

## M1 — What the genuine issue is, and why it needs one read plus your decision

The real defect is presentational and much smaller: the portal profile renders a **"reference" row that is blank for every prepaid customer**, because P2-1 wired `reference = account_number`. For one of the three seeded customers — and for every prepaid customer in production — that row is permanently empty, which reads as a bug to the user even though the data is correct.

`copy.ts` already ships `copy.profile.fields.reference`, and P2-1 rewrote `profile.tsx` in full. **I have not read the shipped v87/v88 `profile.tsx`, so I am not writing this code** — that is rule 1.4, and it is exactly the mistake that produced the `portal-topbar.tsx` failure in P2-1.

Read `Frontend/customer_portal/src/routes/_portal/profile.tsx` first, then pick one:

1. **Hide the row when `account_number` is null.** Smallest change, no new copy, no backend change. The field simply does not exist for prepaid customers — which is the truth.
2. **Fall back to the MSISDN as the reference.** `me_profile_detail` already returns `msisdn`, so no backend change either. Every customer then has a visible identifier, at the cost of two different meanings behind one label.
3. **Label it by plan type.** Most honest, most work: needs a new `copy.ts` key and arguably a `plan_type` field in the projection.

My recommendation is **1** — it is truthful, it is the smallest diff, it needs no new copy string, and it matches the design system's existing `EmptyState`/conditional-row idiom rather than inventing a placeholder. But this is a product judgement about what a customer should see, so it is yours to make, not mine to assume.

Whatever you choose: **no backend change, no migration, and no new seed rows.** `me_profile_detail` is already correct.

---

# §N — Apply order and verification

## N1 — Order

J, K, L and M are independent; this order front-loads the things that unblock the others.

1. **L first** — it is a two-command local repair and it makes `make migrate` / `make test` / `make health` usable for everything that follows. Doing it last means running the whole cookbook with hand-rolled workarounds.
2. **J1 → J3** — infra tier up, then collection bootstrap, then outbox drain. Check `/health` **before** rebuilding anything; if it goes green here, the image was always fine and J2 is unnecessary.
3. **J2** only if `docker images | grep knowledge` is empty or the build actually fails. Rebuild is `make rebuild`; if a zombie container blocks it, `docker rm -f` (removal works where kill does not), then `up -d --build` and `up -d` manually.
4. **J5** — the cross-lingual proof. This is the gate that separates "health returns 200" from "RAG works".
5. **K3 read + `gh run view`**, then **K1**. Read the run before editing the workflow: it may tell you `lint` is already failing for a reason K1 does not address.
6. **M1 read**, then your choice of 1/2/3.

`python -m ruff check --fix` then `python -m ruff check` on anything touched. **No migration in this cookbook** — alembic head stays `0017_notification_failure_reason`. **No Python source change in Bundle J at all** — only the Dockerfile and env.

## N2 — Grep gates, correctly scoped this time

Every gate excludes documentation paths, per §0 rule 2:

```bash
# J2 landed and the CPU index is still the source of the torch wheel
git grep -n "download.pytorch.org/whl/cpu" -- services/ .github/

# the lexical fallback was never enabled to force health green (RED FLAG 3)
git grep -n "KNOWLEDGE_ALLOW_LEXICAL_FALLBACK" -- apps/ services/ infra/ scripts/ Makefile

# no leftover CUDA-index or unpinned torch crept into the workflow
git grep -n "torch" -- .github/
```

The first must show the Dockerfile **and** the new CI step. The second must show **no assignment to `true`** anywhere in live config — a hit in `problems_solving_steps.md` is the documentation of the flag and is expected. The third must show only `torch==2.2.2` with the CPU index.

## N3 — Regression gates (existing suites only — author nothing new)

`ruff` clean · `mypy` clean on anything touched · the existing business-api and persistence suites unchanged · `scripts/verify_p0_1.sh` and `scripts/verify_p0_2.sh` still pass · `make health` at **11/11** once J is complete.

After Bundle L, run `make test` — `scripts/run_tests.py` across all 17 targets — and report the per-target `[ok]/[FAIL]` lines. That inventory has never been executed through `make` on this machine.

**Do not state a test total as a target.** Report what the run prints.

---

# §O — What P2-3 does not close

- **R12** — the GLPI revert (H-3).
- **R14** — persona contract, 5 FAIL / 43 OK.
- **R15** — the mypy `ignore_errors` ratchet across 14 modules and the ruff burn-down. Recorded debt. K3 may force a decision on the mypy half; the ratchet itself stays.
- **R11** — three coexisting definitions of an open invoice. Closed by your decision, not by the code.
- **`sentence-transformers` as an optional extra** — would end H-6 permanently; needs `reranker.py` and `embeddings.py` read first, and is its own bundle.
- **The four `/auth/*` audit routes** are done (P2-2 G4), but auth-session `session_id` is still `None` in those payloads, mirroring `retention.py`. Carry-over rule, not a defect.
- **Demo residue from P2-2's proofs:** `test-client-403@example.tn` exists with password `client-secret-test-55` against customer `2187de39-…` (Yousra), plus its ledger rows. The ledger rows are correct and permanent. The account is a known credential on a demo record — delete the account or rotate its password before this environment is shown to anyone.
- **Still never opened:** 19 of 20 admin routes, most portal routes, `reranker.py`, `embeddings.py`, `retriever.py`, `infra/helm/**`, nine Dockerfiles, and the root `[tool.mypy]` block. Rule 1.4 applies to every one of them.
