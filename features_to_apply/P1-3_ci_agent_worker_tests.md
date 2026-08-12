# P1-3 — CI: make the pipeline actually run

**Branch:** `version_85` @ `752fc4ebb6a80a5dd3f9b93bd50e67c061c8ee21` **plus the local, unpushed P1-2
working tree.**

**Read this before anything else.** P1-2 is applied locally and *not* pushed. P1-3's three target
files — `.github/workflows/ci.yml`, `pyproject.toml`, `scripts/run_tests.py` — appear in P1-2's
"Explicitly NOT touched" list (`ci.yml` by name; the other two by absence from its 8-file modified
list). So the remote copies I read are byte-accurate for those three. **Every measured *number*,
however, must be re-taken locally**, because the working tree now contains P1-2's code, tests and
deletions. Gate 0.8 proves the first claim; gates 0.2–0.7 re-take the numbers.

**Rebuild:** none. **Migration:** none (head stays `0016_portal_identity`). **New dependencies:**
none. **Frontend files touched:** none. **Runtime source logic changed:** none, except
behaviour-preserving ruff *safe* autofixes, bounded by §3.4.

---

## §1 What P1-3 is

The roadmap item is "CI Agent-Worker Tests". Taken literally that is a one-line change. Taken
honestly it is not, because of this:

```yaml
  test:
    needs: [lint]
```

`lint` runs `ruff check .`, which is red. `test` therefore never starts. `docker-build` and
`docker-build-apps` both `need: [test, db-migrations]`, so they never start. `security-scan` needs
both build jobs, so it never starts.

**The pipeline is not partly working. It is dead from the second job onward.** Only `db-migrations`
survives, and only because it declares no `needs`.

Adding the agent-worker suite to a job that never executes would be theatre — a green checkmark on a
run that skipped everything. So P1-3 fixes the blocker first, then wires the tests, then repairs the
build matrix that would have failed the moment the pipeline came back to life.

There is a second reason nobody has noticed: `docker-build`, `docker-build-apps` and `security-scan`
are all gated on `if: github.ref == 'refs/heads/main'`, and every branch in this project is
`version_NN`. Those three jobs have most likely **never executed once**. Their defects are latent,
not observed — and I say "most likely" rather than "never" because I have not read the Actions run
history. Gate 0.10 settles it.

### §1.1 Non-goals — explicitly out of scope

- **No hand-written source edits.** The only source changes permitted are ruff's *safe* autofixes,
  reviewed hunk by hunk under §3.4. Anything ruff classifies as unsafe is out.
- **No `--unsafe-fixes`. Ever.** §0 of the master instruction forbids modifying existing behaviour;
  unsafe fixes are, by ruff's own definition, the ones that can change it.
- **No fix for H-6** (the `knowledge-service` torch hash mismatch). Flagged in §7.1, not touched.
- **No mypy strictness increase.** If mypy is already green, leave the config alone.
- **No merge to `main`,** no release, no tag.
- **No new test files.** P1-3's subject is the pipeline; its proof is a green run.

---

## §2 Coverage disclosure — what I read, and what I did not

Read directly at `version_85` for this patch:

| File | Blob SHA | What it settled |
| --- | --- | --- |
| `.github/workflows/ci.yml` | `a62ea96c` | job graph, `needs`, both matrices, the `file:` paths |
| `pyproject.toml` (root) | `1fbd780a` | ruff select/ignore/exclude, isort first-party, mypy config |
| `scripts/run_tests.py` | `3aa7fb9d` | the 15-entry local test inventory and its PYTHONPATH model |
| `apps/agent-worker/pyproject.toml` | `6f033046` | the 11-extra livekit-agents pin — the CI cost risk |
| `Makefile` | `26ea4077` | the `install` target's package/service/app lists |
| `apps/agent-worker/tests/` | listing | 8 subdirectories + 5 root test files |
| `apps/agent-worker/tests/uat/` | listing | one file, `test_multilingual.py` |
| `apps/agent-worker/tests/resilience/` | listing | `test_chaos_wiring.py`, `test_task_language.py` |
| `apps/token-service/` | listing | **has `tests/` and a `Dockerfile`** |

**Deliberately NOT read, and therefore NOT asserted about:**

- The **body of any agent-worker or token-service test file.** I do not know whether they pass. Gates
  0.6 and 0.7 find out before anything is wired.
- **The 147 ruff errors themselves.** I have only ever seen the count, reported from your machine.
- **mypy's output.** Never measured, by me or in any prior patch. It may be green; it may be the real
  blocker. Gate 0.4 decides.
- **Any of the nine Dockerfiles' contents.** I verified *existence and location* only.
- **The GitHub Actions run history.** Gate 0.10.

### §2.1 The rule this cookbook is written under

In P1-2 I wrote "`escalated` should land near **58**". The true answer was 42: `escalation_cases` has
58 **rows** across 42 **distinct sessions**. I turned a row count into a session-count expectation.
That was the fifth time I have asserted a literal number that turned out wrong, and my standing rule
("assert a location predicate, never a number") was too weak, because it did not cover expectations.

The rule is now stronger, and this document obeys it:

> **Every expected value is expressed as an invariant against a recorded baseline or a query — never
> as a literal.**

So you will not find "147" used as a target anywhere below. You will find `N0`, recorded by gate 0.3.
An invariant checks itself; a literal is a guess wearing a number's clothes.

---

## §0 Pre-flight gates — measure before deciding

P1-3 is the first patch in this series whose *design* depends on numbers I do not have. Run every
gate and record every value **before** making any edit. Several gates can send you back to me.

### 0.1 Baseline is green

```bash
bash scripts/verify_p0_1.sh
bash scripts/verify_p0_2.sh
python -m pytest apps/business-api/tests -q
python -m pytest apps/agent-worker/tests/conversation -q
```

Record all four results. They must match what P1-2 reported. If any differs, **STOP** — something
changed outside this patch and we need to know what before layering on top of it.

### 0.2 Ruff, by rule — the baseline table `R0`

```bash
python -m ruff check . --statistics
```

Record the **entire table verbatim** (count, rule code, description, per row). This is `R0` and it
drives §3 completely. Do not summarise it — I need the rule codes to judge which fixes are safe.

### 0.3 Ruff, total — the baseline count `N0`

```bash
python -m ruff check . --output-format=concise | wc -l
```

Record as `N0`. Also record, separately, the two per-app baselines P1-2 pinned, since §9 re-checks
them:

```bash
python -m ruff check apps/agent-worker/src   # record as W0
python -m ruff check apps/business-api/src   # record as B0
```

### 0.4 Mypy — the unmeasured half of the blocker

```bash
python -m mypy packages/ services/ apps/ 2>&1 | tail -30
```

Record the **final summary line** and the count of errors as `M0`, plus the first ~25 error lines.

**This is a decision gate:**

- **`M0 == 0`** → mypy is not a blocker. Proceed; §3 concerns ruff only.
- **`M0 > 0`** → **STOP and report `M0` plus the error list before editing anything.** Do not sprinkle
  `# type: ignore`, do not weaken `pyproject.toml`, do not guess. The root config already sets
  `disallow_untyped_defs = false` and `ignore_missing_imports = true`, so a non-zero count means real
  type errors, and those are a design conversation, not a lint cleanup.

### 0.5 Enumerate the agent-worker suite

```bash
cd apps/agent-worker
PYTHONPATH=src python -m pytest tests --collect-only -q 2>&1 | tail -30
cd ../..
```

Record the collected count and **every collection error**. The tree has 8 subdirectories
(`callback`, `conversation`, `identity`, `interruption`, `keyterms`, `resilience`, `sentiment`,
`transfer`, `uat`) plus 5 root-level test files. Only `tests/conversation` has ever been run in this
project's history.

### 0.6 Run the agent-worker suite — the gate that decides Item B

```bash
cd apps/agent-worker
PYTHONPATH=src python -m pytest tests -q 2>&1 | tail -40
cd ../..
```

Record pass/fail/error counts **and, if anything fails, which directory it came from.**

**Decision gate:**

- **All green** → wire the whole `tests` directory in §4.
- **Some fail** → **STOP and report the failing files and their errors.** Do not "fix" them as part
  of P1-3, and do not wire a red suite into CI. Two named risks I want you to look for specifically:
  - **`tests/uat/test_multilingual.py`** — the directory name says user-acceptance. If it needs a
    live LiveKit room, a running service, or network, it cannot run in CI.
  - **`tests/resilience/test_chaos_wiring.py`** — "chaos" suggests fault injection, which sometimes
    means timing sensitivity or real sockets.

  If either is environment-dependent, the answer is a scoped exclusion with a recorded reason —
  never a silent skip and never a weakened assertion. Report and I will design it.

### 0.7 Same for token-service

`apps/token-service` has a `tests/` directory and appears in **neither** test inventory.

```bash
cd apps/token-service
PYTHONPATH=src python -m pytest tests -q 2>&1 | tail -20
cd ../..
```

Record the result. Green ⇒ §4 adds it too. Red ⇒ report; it stays out and we handle it separately.

### 0.8 Which other directories have tests nobody runs?

```bash
git ls-files | grep -E "(^|/)tests/" | sed -E 's#/tests/.*##' | sort -u
```

Record the full list. Compare it against the 15 `TARGETS` in `scripts/run_tests.py` and the 13
entries in the CI loop. **Report every directory that has tests but appears in neither.** I already
know of two (`apps/agent-worker`, `apps/token-service`); this gate finds any I missed, and I would
rather be surprised here than in §4.

### 0.9 Confirm P1-3's targets are untouched by P1-2

```bash
git diff --stat HEAD -- .github/workflows/ci.yml pyproject.toml scripts/run_tests.py
```

**Expected: empty output.** This is what licenses me to write byte-exact `oldStr` values from the
remote copies. If it is not empty, **STOP** — my anchors are stale and I must re-read.

### 0.10 Has this workflow ever run?

Open the repository's **Actions** tab and record: whether any run exists, the most recent run's
branch and conclusion, and specifically whether `docker-build` has ever executed. One screenshot or
a three-line summary is enough.

This converts my §1 inference ("most likely never run") into a fact, and it tells us whether §5's
matrix bug is theoretical or has been failing silently on `main` for months.

---

## §3 Item A — the `lint` job blocks everything

### 3.1 The evidence chain

Four links, all from `ci.yml` blob `a62ea96c`:

1. `lint` runs `ruff check .` — no `--exit-zero`, no `continue-on-error`. Non-zero exit fails the job.
2. `test` declares `needs: [lint]` → skipped whenever `lint` fails.
3. `docker-build` and `docker-build-apps` declare `needs: [test, db-migrations]` → skipped.
4. `security-scan` declares `needs: [docker-build, docker-build-apps]` → skipped.

One red rule in one file disables the entire quality gate. That is the single highest-value fix in
P1-3, and it is worth more than the agent-worker wiring that gives the item its name.

### 3.2 The approach, and why it is safe by construction

Ruff classifies every fix as **safe** or **unsafe**. A safe fix is one ruff guarantees preserves
runtime behaviour; unsafe fixes may not. **`ruff check --fix` applies safe fixes only**; unsafe ones
require the explicit `--unsafe-fixes` flag.

That gives us a tool-backed guarantee instead of my judgement, which is exactly what §0's
"do not modify existing behaviour" demands. So:

- **Permitted:** `python -m ruff check . --fix`
- **Forbidden:** `--unsafe-fixes`, any hand-edit of runtime logic to satisfy a rule, any
  `# noqa` added to source.

On that last point — a P0-3 lesson that cost us a cycle: **only ever emit a `# noqa` for a rule in
the `select` list.** The list is `E, F, I, UP, B, C4, SIM, RUF`. A `# noqa` for anything else
(`BLE001`, for instance) is itself flagged as an unused directive. P1-3 adds no `# noqa` at all.

### 3.3 The residue: a ratchet, not a rug

Safe autofixes will not clear everything — `B` and `SIM` findings in particular often need a human.
For the remainder there are three options, and only one is honest:

| Option | Verdict |
| --- | --- |
| `ruff check . --exit-zero` or `continue-on-error: true` | **Rejected.** Makes the job decorative — a green tick that checks nothing. Worse than red, because red is at least truthful. |
| Add the failing rules to the root `ignore` list | **Rejected.** Disables the rule for *new* code too. Today's debt becomes tomorrow's licence. |
| `[tool.ruff.lint.per-file-ignores]` for the exact files that fail today, each with a comment, plus a burn-down list | **Chosen.** Zero code change, fully reversible, and new files are still held to the complete rule set. The debt stays visible and countable instead of disappearing. |

This is a ratchet: the pipeline goes green now, the debt is enumerated, and it can only shrink,
because any *new* violation lands in a file with no ignore entry and fails the build.

### 3.4 Procedure — with a hunk-level review rule

**Step 1 — apply safe fixes.**

```bash
python -m ruff check . --fix
python -m ruff check . --output-format=concise | wc -l   # record as N1
git diff --stat
```

**Step 2 — review every touched file.** This is the important step; do not skim it.

```bash
git diff --name-only
git diff
```

Apply this rule to each hunk:

> **Import reordering, unused-import removal, whitespace, quote/paren normalisation, and literal
> syntax modernisation are ACCEPTED.** Anything that alters control flow, changes a comparison,
> collapses an `if`/`else`, rewrites a comprehension's semantics, or touches an argument list is
> **REJECTED** — `git checkout -- <file>` that file and add a per-file-ignore for it in §3.5 instead.

Ruff should not be producing that second category under `--fix`. If it does, I want to know: record
the file, the rule and the hunk in the results.

**Step 3 — pay particular attention to these paths**, and revert on any doubt:

- `apps/agent-worker/src/**` — the live voice path. A behaviour change here is a broken call.
- `packages/audit-trail/**` — the hash chain. Any change to canonicalisation or ordering breaks
  verification of all 47 existing ledger rows.
- `packages/persistence/src/persistence/models/**` — a changed model is a changed schema contract.
- `apps/business-api/src/business_api/security.py` and `infrastructure/auth/**` — P0-1/P0-2 territory.

**Step 4 — prove nothing broke.** Non-negotiable, and run in this order:

```bash
python -m pytest apps/agent-worker/tests/conversation -q
python -m pytest apps/business-api/tests -q
python scripts/run_tests.py
bash scripts/verify_p0_1.sh
bash scripts/verify_p0_2.sh
```

All must match the 0.1 baseline. **Any regression ⇒ revert the autofix commit entirely and report.**
A lint cleanup is never worth a behavioural regression.

**Step 5 — re-measure.**

```bash
python -m ruff check . --statistics    # record as R1
python -m ruff check apps/agent-worker/src   # must equal W0 or be lower
python -m ruff check apps/business-api/src   # must equal B0 or be lower
```

Both per-app counts must be **≤** their 0.3 baselines. Higher means the fix introduced violations,
which should be impossible — **STOP** if it happens.

### 3.5 Edit — the ratchet in `pyproject.toml`

Only if `N1 > 0`. Generate one entry per still-failing file from `R1`.

Anchor on the existing isort block (blob `1fbd780a`).

`oldStr`:

```toml
[tool.ruff.lint.isort]
```

`newStr`:

```toml
# P1-3 ratchet: pre-existing violations grandfathered per-file so `ruff check .` is green and CI can
# run. New files get no entry here and are held to the full rule set, so this list can only shrink.
# Burn-down tracked in the P1-3 results document. Remove an entry when its file is cleaned.
[tool.ruff.lint.per-file-ignores]
# <one line per file: "path/to/file.py" = ["RULE", ...]>

[tool.ruff.lint.isort]
```

**Rules for generating the entries:**

- Key on the **exact file path** ruff reports, never a glob. `"apps/foo/**"` would grandfather files
  that do not exist yet, which defeats the ratchet.
- List **only** the rule codes that file actually violates.
- Sort alphabetically by path so the diff is reviewable and future removals are obvious.
- If the entry count is large (say, more than ~40 files), **stop and report `R1` before writing
  them** — that would tell us the debt is concentrated somewhere structural and deserves a different
  conversation.

Then confirm the goal:

```bash
python -m ruff check .    # expect: All checks passed!
```

### 3.6 If mypy is red (`M0 > 0`)

Do not proceed past gate 0.4. Report `M0` and the error list. Ruff and mypy are different problems:
ruff has a tool-guaranteed safe-fix mode, mypy does not, and "fixing" type errors means editing
source logic — which §0 forbids without approval. We decide that together.

### 3.7 Safety

| Concern | Why it is contained |
| --- | --- |
| Autofix changes behaviour | Only ruff-classified *safe* fixes; hunk-level review; full suite re-run; revert-on-regression |
| Ratchet hides real problems | Per-file and per-rule, never global; enumerated in the results; new code unaffected |
| Lint passes but means nothing | Rejected `--exit-zero` explicitly; the rule set is unchanged for all new code |
| A fix lands in the voice path | §3.4 step 3 names `agent-worker/src` first; conversation suite re-run |
| Audit chain disturbed | `audit-trail` named in step 3; `verify_p0_1.sh` re-run, which exercises the ledger |

---

## §4 Item B — one test inventory, not three

### 4.1 The divergence

There are two hardcoded inventories and they do not agree with each other or with reality.

| Target | CI `test` loop | `scripts/run_tests.py` | Has a `tests/` dir |
| --- | :---: | :---: | :---: |
| `packages/audit-trail` | ✅ | ✅ | yes |
| `packages/service-auth` | ✅ | ✅ | yes |
| `packages/cache` | ✅ | ✅ | yes |
| `packages/object-storage` | ✅ | ✅ | yes |
| `packages/integration-adapters` | ✅ | ✅ | yes |
| `packages/persistence` | ✅ | ✅ | yes |
| `packages/observability-kit` | ❌ | ✅ | yes |
| `services/context-service` | ✅ | ✅ | yes |
| `services/decision-service` | ✅ | ❌ | ? (gate 0.8) |
| `services/policy-service` | ✅ | ✅ | yes |
| `services/execution-service` | ✅ | ✅ | yes |
| `services/notification-service` | ✅ | ✅ | yes |
| `services/knowledge-service` | ✅ | ✅ | yes |
| `mcp-servers/ticketing-glpi` | ❌ | ✅ | yes |
| `apps/business-api` | ✅ | ✅ | yes |
| **`apps/agent-worker`** | **❌** | **❌** | **yes — 8 dirs + 5 files** |
| **`apps/token-service`** | **❌** | **❌** | **yes** |

Three separate failures in one table: CI silently skips `observability-kit` and `ticketing-glpi`;
`make test` silently skips `decision-service`; and **both** skip the two apps. A developer running
`make test` locally and a reviewer reading a green CI run are looking at different, incomplete
pictures — and neither has ever seen the agent-worker suite.

### 4.2 The fix: make the script the single source of truth

Rather than adding agent-worker to two lists that will drift again, delete one of the lists.
`scripts/run_tests.py` becomes the only inventory, and CI calls it. After this, local and CI test
exactly the same set **by construction** — drift stops being possible rather than being discouraged.

This also matches how the repo already thinks: `make test` is `python scripts/run_tests.py`.

### 4.3 Edit 1 — `scripts/run_tests.py`, add the missing targets

Only add targets that gates 0.6/0.7/0.8 proved green. The agent-worker tuple needs the shared
package sources on `PYTHONPATH`, matching the imports its `pyproject.toml` declares
(`object-storage`, `service-auth`, `audit-trail`, `persistence`, `domain-core`, `observability-kit`).

`oldStr`:

```python
    ("apps/business-api", ["../../packages/object-storage/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src"], "tests"),
]
```

`newStr`:

```python
    ("apps/business-api", ["../../packages/object-storage/src", "../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src"], "tests"),
    # P1-3: the agent-worker suite existed but was run by nothing — not by `make test`, not by CI.
    ("apps/agent-worker", ["../../packages/persistence/src", "../../packages/audit-trail/src", "../../packages/domain-core/src", "../../packages/observability-kit/src", "../../packages/object-storage/src", "../../packages/service-auth/src"], "tests"),
    ("apps/token-service", [], "tests"),
    # P1-3: present in CI's loop but missing here — the two inventories had drifted apart.
    ("services/decision-service", ["../../packages/persistence/src", "../../packages/domain-core/src", "../../packages/service-auth/src"], "tests"),
]
```

**Three conditions on this edit:**

1. Include the `apps/token-service` line **only if** gate 0.7 was green.
2. Include the `services/decision-service` line **only if** gate 0.8 confirms it has a `tests/`
   directory — and if its PYTHONPATH needs differ from my guess, use what actually works and record
   the change. I inferred those three paths from the other services' patterns; I have not read
   `decision-service`'s imports.
3. If gate 0.8 found targets I did not list, **report them before adding** — do not improvise
   PYTHONPATH tuples.

Then prove it locally:

```bash
python scripts/run_tests.py
```

Every line must print `[ok]`, ending in `All suites passed.`

### 4.4 The dependency cost — the real risk in this item

`apps/agent-worker/pyproject.toml` pins:

```
livekit-agents[deepgram,elevenlabs,azure,openai,google,silero,turn-detector,gladia,cartesia,inworld,smallestai]==1.6.5
```

**`silero` and `turn-detector` pull ML runtimes — onnxruntime, and potentially torch.** That is the
same dependency family as H-6, the pre-existing `knowledge-service` build failure. Installing this in
CI means a materially slower job and a new class of flakiness.

Options considered:

| Option | Verdict |
| --- | --- |
| Install the full pinned extras in CI | **Chosen.** It is the only option that tests what actually ships. |
| Install `livekit-agents` with reduced extras for CI | **Rejected.** Creates a second dependency truth; CI would pass against software nobody runs. |
| Give agent-worker its own CI job | **Rejected for now,** but kept as the escape hatch in §4.6. It re-splits the inventory we just unified. |

Mitigation for the chosen option: enable pip caching, which `actions/setup-python` supports natively
and which the workflow does not currently use.

### 4.5 Edit 2 — `.github/workflows/ci.yml`, the `test` job

Replace the inline loop with the script, and install every target's dependencies up front. The
install list mirrors the `Makefile`'s `install` target (`SERVICES` + `MCP` + `agent-worker`), which
is how a developer's machine is already set up.

> **Note the model change.** The old loop ran `pip install -q .` *inside* each target directory.
> `run_tests.py` does not install anything — it sets `PYTHONPATH` and runs pytest. So the install
> must happen up front, or third-party dependencies will be missing. This is the single most likely
> way to get this edit wrong.

`oldStr`:

```yaml
  test:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install shared packages + tooling
        run: |
          pip install --upgrade pip
          pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
                      ./packages/pii-shield ./packages/observability-kit ./packages/service-auth \
                      ./packages/cache ./packages/object-storage ./packages/notification-client \
                      ./packages/integration-adapters
      - name: Offline test suite
        run: |
          set -e
          for pkg in packages/audit-trail packages/service-auth packages/cache packages/object-storage \
                     packages/integration-adapters packages/persistence \
                     services/context-service services/decision-service services/policy-service \
                     services/execution-service services/notification-service services/knowledge-service \
                     apps/business-api ; do
            echo "== $pkg ==" ; ( cd "$pkg" && pip install -q . && python -m pytest -q ) || exit 1
          done
```

`newStr`:

```yaml
  test:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install shared packages + tooling
        run: |
          pip install --upgrade pip
          pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
                      ./packages/pii-shield ./packages/observability-kit ./packages/service-auth \
                      ./packages/cache ./packages/object-storage ./packages/notification-client \
                      ./packages/integration-adapters
      # P1-3: run_tests.py sets PYTHONPATH but installs nothing, so every target's third-party
      # dependencies must be present first. This list mirrors the Makefile `install` target.
      - name: Install services, MCP servers and apps
        run: |
          pip install ./services/context-service ./services/knowledge-service ./services/decision-service \
                      ./services/policy-service ./services/execution-service ./services/notification-service \
                      ./apps/token-service ./apps/business-api
          pip install ./mcp-servers/ai-knowledge-rag ./mcp-servers/ticketing-glpi ./mcp-servers/messaging-gateway
          pip install ./apps/agent-worker
      # P1-3: single source of truth. `make test` and CI now run the identical inventory, so the two
      # can no longer drift. Adding a target in run_tests.py is enough to add it to CI.
      - name: Offline test suite
        run: python scripts/run_tests.py
```

### 4.6 If the CI install is too slow or fails

If the agent-worker install blows the job's time budget or fails on an ML wheel, the escape hatch is
a dedicated job — **not** a reduced extras set, and **not** dropping the suite:

```yaml
  test-agent-worker:
    runs-on: ubuntu-latest
    needs: [lint]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install ./packages/domain-core ./packages/persistence ./packages/audit-trail \
                         ./packages/observability-kit ./packages/service-auth ./packages/object-storage
      - run: pip install ./apps/agent-worker
      - run: PYTHONPATH=src python -m pytest tests -q
        working-directory: apps/agent-worker
```

If you take this path, also add `test-agent-worker` to the `needs:` of `docker-build` and
`docker-build-apps`, and say so in the results — otherwise the worker suite becomes advisory and the
build can ship past a red test.

**Report before choosing this.** It re-splits the inventory §4.2 just unified, and that tradeoff is
mine to weigh, not yours to absorb silently.

---

## §5 Item C — `docker-build` looks for three Dockerfiles that do not exist

### 5.1 The bug

`docker-build` runs a nine-entry matrix through a single hardcoded path:

```yaml
          file: services/${{ matrix.service }}/Dockerfile
```

Six of those nine live under `services/`. **Three do not.** Verified by directory listing at
`version_85`:

| Matrix entry | Path the job builds | Reality |
| --- | --- | --- |
| `token-service` | `services/token-service/Dockerfile` | actually `apps/token-service/Dockerfile` (894 B) |
| `business-api` | `services/business-api/Dockerfile` | actually `apps/business-api/Dockerfile` |
| `agent-worker` | `services/agent-worker/Dockerfile` | actually `apps/agent-worker/Dockerfile` |

Those three legs cannot succeed — the build context has no such file.

### 5.2 They are already built correctly, one job below

`docker-build-apps` runs the *same three* with the *correct* path:

```yaml
          file: apps/${{ matrix.service }}/Dockerfile
```

and pushes **identical tags** — `ghcr.io/<repo>/<service>:<sha>` and `:latest`. So the three apps are
not merely built from a wrong path; they are built twice, once impossibly and once correctly, both
racing for the same `:latest` tag. Removing them from `docker-build` fixes the path bug and the
duplicate push in one edit, and removes nothing: `docker-build-apps` already covers them.

### 5.3 Edit — trim `docker-build`'s matrix to the six real services

The nine-entry list appears **twice** in the file (here and in `security-scan`), so the `oldStr`
below deliberately runs through the `file:` line to stay unique. Copy it exactly.

`oldStr`:

```yaml
    strategy:
      matrix:
        service:
          - context-service
          - decision-service
          - policy-service
          - execution-service
          - knowledge-service
          - notification-service
          - token-service
          - business-api
          - agent-worker
    steps:
      - uses: actions/checkout@v4
      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: services/${{ matrix.service }}/Dockerfile
```

`newStr`:

```yaml
    strategy:
      matrix:
        # P1-3: only the six that actually live under services/. token-service, business-api and
        # agent-worker live under apps/ and are built by docker-build-apps with the correct path;
        # listing them here built them from a non-existent file and double-pushed the same tags.
        service:
          - context-service
          - decision-service
          - policy-service
          - execution-service
          - knowledge-service
          - notification-service
    steps:
      - uses: actions/checkout@v4
      - name: Log in to registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build and push
        uses: docker/build-push-action@v6
        with:
          context: .
          file: services/${{ matrix.service }}/Dockerfile
```

### 5.4 `security-scan`'s nine-entry matrix is correct — do not touch it

It looks like the same mistake, and it is not. `security-scan` consumes **image tags**, not Dockerfile
paths:

```yaml
          image-ref: ${{ env.REGISTRY }}/${{ github.repository }}/${{ matrix.service }}:${{ env.IMAGE_TAG }}
```

All nine images exist after `docker-build` (six) and `docker-build-apps` (three), and the job
`needs:` both. Its list of nine is exactly right. Trimming it to match §5.3 would silently stop
scanning the three apps — a security regression dressed as consistency. **Leave it alone.**

### 5.5 This is latent, not observed

`docker-build`, `docker-build-apps` and `security-scan` all carry `if: github.ref ==
'refs/heads/main'`. Every branch in this project is `version_NN`, and `test` has been skipped since
the lint job went red regardless. Gate 0.10 confirms whether these jobs have ever executed. Record
the answer either way — if they *have* run on `main`, three legs have been failing in public and
that changes how urgently the rest of §5 matters.

---

## §6 Item D — CI never runs on the branches the work happens on

```yaml
on:
  push:
    branches: [ main ]
  pull_request:
```

Pushes to `version_83`, `version_84`, `version_85` trigger nothing. Only pull requests do, and this
project has been shipping by pushing branches. **P1-3's own fix would therefore never be exercised**
until someone opened a PR — which makes this the edit that gives all the others feedback.

`oldStr`:

```yaml
on:
  push:
    branches: [ main ]
  pull_request:
```

`newStr`:

```yaml
on:
  push:
    # P1-3: work happens on version_NN branches, so main-only meant CI never ran on the code being
    # written. lint/test/db-migrations now run per push; the build and scan jobs stay main-only via
    # their own `if:` guards, so this costs no registry pushes.
    branches: [ main, 'version_*' ]
  pull_request:
```

**This is the one edit in P1-3 that is safe to skip** if you would rather not spend Actions minutes
on every push. It changes no behaviour of the code, only when the pipeline observes it. It costs
nothing in registry terms, because `docker-build`, `docker-build-apps` and `security-scan` keep their
own `if: github.ref == 'refs/heads/main'` guards and will still skip on `version_*`. Say which way
you went in the results.

---

## §7 Flagged, not changed

### 7.1 H-6 — `knowledge-service` cannot build (torch hash mismatch)

Pre-existing, recorded since P0-3: `torch==2.2.2` fails hash verification from
`download-r2.pytorch.org` (expected `431a747b5a…`, got `5421564bfe…`). `knowledge-service` remains in
`docker-build`'s matrix after §5.3, so if the mismatch is not specific to your machine's mirror, that
leg will fail the first time the job runs.

**Not fixed here** — it is a dependency-pinning problem, not a CI-wiring one, and fixing it means
changing a pin, which §0 puts behind approval. **Gate:** when the pipeline first runs (§9.3), record
whether `knowledge-service` built. GitHub's runners use a different mirror, so it may simply succeed
there — which would be worth knowing, since it would localise H-6 to your network.

### 7.2 `db-migrations` does not seed credentials

The job runs `alembic upgrade head`, `seed_pilot`, `seed_reference`. P1-2 added
`seed_auth_credentials` and `seed_admin` to `make seed`, so the Makefile and CI have now drifted the
same way §4.1 describes for tests.

It is arguably fine — the job's purpose is proving migrations apply, not producing a usable
environment. But `seed_auth_credentials` also exercises the `auth` schema that P0-1 introduced, and
that is worth covering.

**Gate before adding anything:** does `seed_auth_credentials` run without `ADMIN_*` environment
variables?

```bash
cd packages/persistence && python -m seed.seed_auth_credentials --help 2>&1 | head -5
```

- Needs no secrets ⇒ propose adding it to the job and report the diff. **Do not apply it in this
  patch** — report and I will fold it in.
- Needs secrets ⇒ leave it out. `seed_admin` reads `ADMIN_EMAIL`/`ADMIN_PASSWORD` and **must not** be
  added: that would require putting real admin credentials into CI, and H-4 already flags
  `ADMIN_PASSWORD` as a credential pending rotation.

### 7.3 Mypy strictness

`disallow_untyped_defs = false` with a `# pragmatic: enable per-package as coverage grows` comment.
Raising it is a deliberate future project, not a side effect of a CI patch. Untouched.

### 7.4 No inventory drift-guard

§4.2 makes drift impossible *between CI and `make test`*, because both now read one list. It does not
stop someone adding `services/new-thing/tests/` and forgetting `run_tests.py`. A guard — a check that
every directory containing `tests/` appears in `TARGETS` — would close that, and gate 0.8 is
essentially that check run by hand. **Recorded as a P2 follow-up**, not built here: P1-3 should not
invent a new test genre while fixing the pipeline that runs them.

### 7.5 P1-2 is unpushed

When you eventually push, P1-2 and P1-3 land together and the first CI run will be judging both. If
that run is red, bisect before assuming P1-3 caused it — P1-2 changed `server.py`, `session_state.py`,
`retention.py`, the `Makefile`, `Procfile`, two dev scripts, and deleted 29 files.

---

## §8 Tests

**No new test files.** P1-3's subject is the pipeline; inventing a test to test the test runner would
add a file for the pleasure of adding one. Its proof is that the suites *already in the repo* run,
and that the pipeline goes green.

What P1-3 does add is coverage, and it is substantial: the agent-worker suite (8 directories plus 5
root files) and the token-service suite have **never** run in CI or in `make test`. Record the exact
before/after collected counts from gates 0.5–0.7 in the results — that delta is this patch's real
output.

---

## §9 Verification

### 9.1 Static, local — all must hold

```bash
python -m ruff check .                         # expect: All checks passed!
python -m ruff check apps/agent-worker/src     # ≤ W0 from gate 0.3
python -m ruff check apps/business-api/src     # ≤ B0 from gate 0.3
python -m mypy packages/ services/ apps/       # equals M0 from gate 0.4
python scripts/run_tests.py                    # every line [ok], "All suites passed."
python -m pytest apps/business-api/tests -q    # equals the 0.1 baseline
python -m pytest apps/agent-worker/tests -q    # equals the 0.6 baseline
bash scripts/verify_p0_1.sh                    # 20/20
bash scripts/verify_p0_2.sh                    # 9/9
```

Note the form of every expectation: *equals the recorded baseline*, never a literal. If you find
yourself comparing against a number written in this document, I made a mistake — tell me.

### 9.2 The workflow file is valid YAML

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"
```

PyYAML is usually present transitively. If it is not, do **not** install it — skip this check and say
so; §9.3 catches syntax errors anyway, just later and louder.

Then confirm the §5 edit did what it should:

```bash
git diff .github/workflows/ci.yml
grep -n "file: services/\|file: apps/" .github/workflows/ci.yml
grep -c "          - agent-worker" .github/workflows/ci.yml
```

The second command must show exactly the two `file:` lines, unchanged in form. The third must show
`agent-worker` still present in `docker-build-apps` and `security-scan`, and gone from `docker-build`
— read the surrounding context to confirm *which* occurrences remain rather than trusting the count.

### 9.3 The honest limit of this patch

**Everything above is static.** P1-3 changes a CI workflow, and a CI workflow's only real proof is a
run on GitHub — which needs a push, which you have deferred until the feature work is done.

So, plainly, and in the language of the §13 absolute rules: **P1-3 will be *inspected and locally
verified*, not *verified*.** I will not describe the pipeline as fixed until a run is green. When you
do push, capture: which jobs ran, which passed, the `test` job's duration (the §4.4 install cost),
and whether `knowledge-service` built (§7.1). Those four facts close P1-3 properly.

If you would like it closed sooner, the smallest sufficient action is a single push of the working
branch after §6's trigger edit — no PR, no merge, no release. That is a one-line ceremony rather than
the full commit process you deferred, and it is the only way to earn the word "verified" here.

---

## §10 Apply order

1. Gates 0.1–0.10. Record every value. Honour every STOP.
2. If `M0 > 0` → stop and report. Do not continue.
3. If gate 0.6 or 0.7 is red → stop and report. Do not continue to §4.
4. `ruff check . --fix` (§3.4 step 1).
5. Review every hunk (§3.4 steps 2–3). Revert anything outside the accepted categories.
6. Re-run the full suite set (§3.4 step 4). Regression ⇒ revert everything and report.
7. Re-measure ruff (§3.4 step 5).
8. If residue remains → write the `per-file-ignores` ratchet (§3.5). More than ~40 files ⇒ report first.
9. `python -m ruff check .` → must be clean.
10. Edit `scripts/run_tests.py` (§4.3), honouring its three conditions.
11. `python scripts/run_tests.py` → all `[ok]`.
12. Edit `ci.yml` `test` job (§4.5).
13. Edit `ci.yml` `docker-build` matrix (§5.3).
14. Edit `ci.yml` triggers (§6) — or skip deliberately and say so.
15. Verification §9.1 and §9.2.
16. Write the §15 completion report.

Steps 4–9 and 10–14 are independent; do them in this order anyway, so that if the suite goes red at
step 11 you know the autofix was already proven clean at step 6.

---

## §11 Rollback

| Change | Undo |
| --- | --- |
| ruff autofixes | `git checkout -- <files from git diff --name-only>`, or revert the whole commit |
| `per-file-ignores` block | delete the block from `pyproject.toml`; nothing else reads it |
| `run_tests.py` targets | remove the added tuples; the file returns to its 15 entries |
| `ci.yml` `test` job | restore the inline loop from blob `a62ea96c` |
| `ci.yml` matrix | re-add the three app entries — though that restores a known-broken state |
| `ci.yml` triggers | restore `branches: [ main ]` |

No migration, no schema change, no container rebuild, no data touched. Every item is a text revert,
and nothing in P1-3 can affect a running service: the workflow file is inert outside GitHub Actions,
and `run_tests.py` is a developer tool. **The only change that can reach runtime is the ruff autofix**
— which is why §3.4 spends four steps on it.

---

## §12 Impact and risk

**What gets better**

- CI runs at all, for the first time in the history of the branches we have been working on.
- The agent-worker suite — the code that handles live calls — is tested by automation instead of by
  hand, in one directory, occasionally.
- `make test` and CI become the same thing, permanently.
- `token-service`, `observability-kit` and `ticketing-glpi` stop being silently skipped.
- Three impossible build legs and a duplicate `:latest` push disappear.

**Risk register**

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| An autofix changes behaviour | Low | safe fixes only; hunk review; full suite; revert-on-regression (§3.4) |
| Agent-worker suite is red today | **Unknown — never run** | gate 0.6 stops the patch before wiring it |
| `uat`/`resilience` need live infrastructure | Medium | gate 0.6 names them specifically; report, do not skip |
| CI install too slow or fails on ML wheels | Medium | pip cache; §4.6 escape hatch, reported not applied |
| `knowledge-service` fails on torch | Medium | §7.1: flagged, out of scope, observed on first run |
| Ratchet grandfathers too much | Low | per-file and per-rule; >40 files ⇒ stop and report |
| YAML typo breaks the workflow | Low | §9.2 parse check plus diff review |
| My `decision-service` PYTHONPATH guess is wrong | **Medium — inferred, not read** | §4.3 condition 2: use what works, record the change |

That last row is deliberate. I inferred those three paths from sibling entries without reading
`decision-service`'s imports, and I would rather label it than let it read as verified.

---

## §13 Confidence

| Item | Confidence | Basis |
| --- | --- | --- |
| §5 matrix fix | **High** | all six paths verified by directory listing; the bug is arithmetic |
| §5.4 leaving `security-scan` alone | **High** | it consumes tags, not paths; read the job |
| §6 trigger fix | **High** | four lines, no code effect |
| §4.5 CI `test` rewrite | **Medium-high** | the install-model change is the risk, and §4.5 calls it out |
| §4.3 agent-worker tuple | **Medium** | PYTHONPATH derived from declared dependencies; gate 0.6 proves it |
| §4.3 decision-service tuple | **Low-medium** | inferred from siblings; explicitly conditional |
| §3 ruff to green | **Medium** | mechanism sound and tool-guaranteed; the 147 contents are unmeasured |
| §3.6 mypy | **Unknown by design** | never measured; gate 0.4 stops the patch rather than guessing |
| Pipeline actually green | **Unproven until pushed** | §9.3 |

---

## §14 File manifest

**Modified — known in advance (3):**

1. `.github/workflows/ci.yml` — `test` job rewrite (§4.5), `docker-build` matrix (§5.3), triggers (§6)
2. `scripts/run_tests.py` — up to three added target tuples (§4.3)
3. `pyproject.toml` — `per-file-ignores` ratchet, **only if `N1 > 0`** (§3.5)

**Modified — cannot be listed in advance:** whatever `ruff check . --fix` touches. I have not read
the 147 findings, so naming files here would be a guess. Enumerate them at apply time:

```bash
git diff --name-only
```

and paste that list into the results as the authoritative record. This is §2.1's rule applied to a
manifest: an invariant that produces the answer, not a literal that pretends to know it.

**Created:** none. **Deleted:** none.

**Explicitly NOT touched:** every file under `apps/agent-worker/src` and `apps/business-api/src`
except as an accepted ruff autofix · `security-scan`'s matrix (§5.4) · `docker-build-apps` ·
`db-migrations` (§7.2) · the mypy config (§7.3) · any Dockerfile · any dependency pin · any migration
· anything under `Frontend/` · `Makefile` · `status.ts` · `.env` · `.env.example`.

---

## §15 Completion report to return

1. Gates 0.1–0.10, every recorded value — including the full `R0` statistics table and `M0`.
2. Gate 0.5/0.6 output: what the agent-worker suite collects, and what it does when run. **This has
   never been observed before; it is the most interesting number in the patch.**
3. Gate 0.7: token-service result. Gate 0.8: any test directory in neither inventory.
4. Gate 0.10: has this workflow ever run, and has `docker-build` ever executed.
5. `git diff --name-only` after the autofix — the authoritative modified-file list.
6. Any hunk you rejected under §3.4's review rule, with the file and rule code.
7. `N0 → N1`, and the final `ruff check .` result.
8. The `per-file-ignores` block as written, or a statement that none was needed.
9. `python scripts/run_tests.py` output — every line.
10. §9.1's nine results, each against its recorded baseline.
11. §9.2 YAML parse result, or a note that PyYAML was absent.
12. Whether you applied or skipped §6, and why.
13. Whether §4.6's escape hatch was needed.
14. §7.2 gate: does `seed_auth_credentials` need secrets.
15. An explicit statement that the pipeline is **inspected and locally verified, not verified**,
    unless a run happened — in which case, the four facts from §9.3.

---

## §16 Handoff — what P2-1 inherits

P1-3 closes the P1 tier. **P2-1 is the dashboard/UX work, and its binding instruction is to read
`ROADMAP_admin_dashboard_no_constraints.md` completely before designing anything** — that document,
not this one and not my memory, is the source of truth for what the admin dashboard should become.

Carried forward into P2-1:

- **The portal still shows "Amara Osei"** from `fixtures/customer.ts` to a signed-in client. P0-1 built
  real `/me/*` endpoints; nothing consumes them yet. This is the most visible remaining lie in the UI.
- **`item.interrupted`** is recorded but unpersisted — needs a column, so it needs a migration.
- **FEATURE_19** (notification failure reason) also needs a migration; the two could share one.
- **The 60 pre-existing prettier errors** in the customer portal.
- **`system_overview()`'s eleven hardcoded `"online"` strings** — runbook D6. Still no claim from me
  about what the admin overview renders; that needs the component read first.
- **The ORB display-quality change** shipped in v84 has never been reviewed by anyone.
- **The drift-guard** from §7.4.

And three conventions this patch adds to the standing list:

1. **Never hand-format imports in a file you author.** I got isort wrong in two consecutive patches —
   P0-3 needed a blank line added, P1-2 needed one removed. Write the file, then run
   `python -m ruff check --fix <file>` and let the tool settle it.
2. **Never state an expected value as a literal.** Express it as an invariant against a recorded
   baseline or a query. The P1-2 "58" was a row count masquerading as a session count.
3. **When asserting that nothing references something, name the search rather than the conclusion.**
   In P1-2 I wrote that the `Makefile` was supervisor-dashboard's only live reference; `Procfile` and
   two dev scripts also referenced it. The claim was wrong and the gate caught it — which is the
   argument for writing gates that can falsify me.
