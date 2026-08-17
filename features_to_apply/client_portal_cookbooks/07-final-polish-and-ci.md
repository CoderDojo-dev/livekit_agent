# COOKBOOK 7 — FINAL POLISH AND CI READINESS

**Files touched:** `.github/workflows/ci.yml` (one new job + one matrix note), `Frontend/customer_portal/package.json` (scripts only), optional `scripts/run_tests.py` (one entry), plus the verification matrix below.
**Nothing here changes runtime behaviour.**

---

## 7.0 The CI file as it actually is on `version_92` (verified)

`.github/workflows/ci.yml`, jobs in dependency order:

| Job | Trigger | What it does |
|---|---|---|
| `lint` | every push to `main` / `version_*`, every PR | `pip install ruff mypy`; `ruff check .`; **`mypy packages/ services/ apps/`** |
| `frontend-test` | same | `Frontend/admin_dashboard` only: node **22.12.0**, `npm ci`, `npm run typecheck`, `npm run lint`, `npm test`, `npm run build` |
| `test` | needs `lint` | installs every package/service/app, then `python scripts/run_tests.py` |
| `db-migrations` | same | postgres:16 service, `alembic upgrade head`, `seed.seed_pilot`, `seed.seed_reference` |
| `docker-build` / `docker-build-apps` | `main` only | 6 images from `services/`, 3 from `apps/` |
| `security-scan` | `main` only | Trivy over all 9 images |

Four consequences for this plan, all of them load-bearing:

1. **`mypy packages/ services/ apps/` already covers `apps/business-api`.** The new `me_reads.py` from Cookbook 3 must type-check under the repo’s existing mypy settings on the first push, or CI goes red on a branch that has nothing to do with the frontend.
2. **`ruff check .` runs at the repo root** — it also lints the new file.
3. **`python scripts/run_tests.py` is the single source of truth for the Python suite** (the comment in the file says so explicitly: *“Adding a target in run_tests.py is enough to add it to CI”*). Any test added for `me_reads.py` must be registered there or it silently never runs.
4. **The portal job does not exist yet, and `push` already includes `version_*`** — so the moment the job is added, it runs on the implementation branch. That is exactly the intent, and it is also why the job must be added **last**, after the portal is green locally.

---

## 7.1 Preflight — what the portal must be able to do before CI can run it

```sh
cd Frontend/customer_portal

# 1. Which lockfile exists? The cache-dependency-path below must match exactly,
#    and `npm ci` requires a package-lock.json specifically.
ls -1 package-lock.json bun.lockb pnpm-lock.yaml yarn.lock 2>/dev/null

# 2. Which scripts exist? admin_dashboard's job calls typecheck, lint, test, build.
node -e "console.log(Object.keys(require('./package.json').scripts))"

# 3. Compare the two manifests' script sets — the new job must not invent a script.
diff <(node -e "console.log(Object.keys(require('./package.json').scripts).sort().join('\n'))") \
     <(node -e "console.log(Object.keys(require('../admin_dashboard/package.json').scripts).sort().join('\n'))")
```

Three outcomes and their fixes:

* **No `package-lock.json`** (likely, this is a Lovable export). Generate one with `npm install` on the target node version and commit it. Without it `npm ci` fails immediately, and `cache: npm` has nothing to key on. Do not switch the job to `npm install` — it would defeat the point of a reproducible CI install.
* **No `typecheck` script.** Add it; do not make the job call `tsc` directly, because then the local command and CI diverge.
* **No `test` script / no test runner.** Options in §7.3. Do **not** copy `npm test` into the job and let it fail.

---

## 7.2 `package.json` scripts (additive only)

```diff
   "scripts": {
     "dev": "vite dev --port 8080",
     "build": "vite build",
-    "lint": "eslint ."
+    "lint": "eslint .",
+    "typecheck": "tsc --noEmit",
+    "test": "vitest run --passWithNoTests"
   },
```

Keep the existing `dev`/`build`/`preview` lines exactly as they are — only add. Mirror whatever names `admin_dashboard` uses so one mental model covers both frontends.

> `--passWithNoTests` is deliberate: it lets the CI job be added **before** the first test exists, so the typecheck/lint/build gate starts protecting the branch immediately. Remove the flag once §7.3’s tests land.

### `tsc --noEmit` will fail the first time

Expect and fix these, in this order:

1. `routeTree.gen.ts` is generated. `/logout` (Cookbook 2) is a **new route file**, so the tree must be regenerated — run `npm run dev` once and commit the regenerated file, or CI will type-check a tree that has no `/logout`.
2. The repo tracks `tsconfig.tsbuildinfo` (noted in Cookbook 1). Add it to `.gitignore` and `git rm --cached` it; a stale buildinfo can mask errors locally that CI then finds.
3. Server-function return types: `createServerFn().handler()` infers through Zod. If inference degrades to `any`, annotate the handler return type explicitly, as `voice.server.ts` does (`Promise<VoiceGrant>`).
4. `motion/react` `layoutId` on a conditionally rendered element (the tab underline) type-checks, but a `motion.span` inside `AnimatePresence` needs a stable `key`. Add one if `tsc` or the lint rule complains.

---

## 7.3 Frontend tests — the four that are worth writing

These are the pure, dependency-free units where a regression would be invisible in review and expensive in production. Nothing here needs a DOM, a network, or LiveKit.

**Add** `src/lib/orb-state.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { toOrbState } from "./orb-state";
import type { AgentState } from "@livekit/components-react";

describe("toOrbState", () => {
  it("maps every LiveKit agent state to a distinct orb state", () => {
    const pairs: Array<[AgentState, string]> = [
      ["disconnected", "disconnected"],
      ["connecting", "connecting"],
      ["pre-connect-buffering", "preConnect"],
      ["initializing", "initializing"],
      ["idle", "idle"],
      ["listening", "listening"],
      ["thinking", "thinking"],
      ["speaking", "speaking"],
      ["failed", "failed"],
    ];
    for (const [agentState, orbState] of pairs) {
      expect(toOrbState(agentState, true)).toBe(orbState);
    }
    // Nine in, nine distinct out: the orb has no unreachable state.
    expect(new Set(pairs.map(([, orb]) => orb)).size).toBe(9);
  });

  it("never freezes on an unknown state", () => {
    expect(toOrbState(undefined, false)).toBe("disconnected");
    expect(toOrbState(undefined, true)).toBe("idle");
    expect(toOrbState("something-new" as AgentState, true)).toBe("idle");
  });
});
```

**Add** `src/lib/tool-events.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { parseToolEvent, timestampMs, toolEventText } from "./tool-events";

const valid = {
  version: 1,
  kind: "tool",
  id: "call_1",
  name: "get_balance_summary",
  label: "Reading Balance Information",
  status: "done",
  created_at: 1_700_000_000,
};

describe("parseToolEvent", () => {
  it("accepts the exact frontend_events.py payload", () => {
    expect(parseToolEvent(JSON.stringify(valid))?.name).toBe("get_balance_summary");
  });

  it("rejects anything else without throwing", () => {
    for (const bad of [
      "not json",
      "{}",
      JSON.stringify({ ...valid, version: 2 }),
      JSON.stringify({ ...valid, kind: "persona" }),
      JSON.stringify({ ...valid, status: "running" }),
    ]) {
      expect(parseToolEvent(bad)).toBeNull();
    }
  });
});

describe("toolEventText", () => {
  it("never leaks a tool name", () => {
    const names = [
      "knowledge_search", "get_invoice_summary", "get_balance_summary",
      "get_plan_details", "route_to_billing", "route_to_technical",
      "escalate_to_manager", "verify_with_known_element", "record_consent",
      "change_plan", "execute_payment", "unblock_sim", "replace_sim",
      "create_ticket", "schedule_callback",
    ];
    for (const name of names) {
      for (const status of ["done", "error"] as const) {
        const text = toolEventText({ ...valid, name, status } as never);
        expect(text).not.toContain("_");
        expect(text.length).toBeGreaterThan(3);
      }
    }
  });

  it("falls back to the worker label, then to generic copy", () => {
    expect(toolEventText({ ...valid, name: "brand_new_tool" } as never)).toBe(
      "Reading Balance Information",
    );
    expect(
      toolEventText({ ...valid, name: "brand_new_tool", label: "Service action" } as never),
    ).toBeTruthy();
  });
});

describe("timestampMs", () => {
  it("normalises seconds and milliseconds", () => {
    expect(timestampMs(1_700_000_000)).toBe(1_700_000_000_000);
    expect(timestampMs(1_700_000_000_000)).toBe(1_700_000_000_000);
  });
});
```

**Add** `src/lib/format.test.ts` — TND is a three-decimal currency and `Africa/Tunis` is the operational zone; both are easy to regress:

```ts
import { describe, expect, it } from "vitest";
import { duration, money, quantity } from "./format";

describe("format", () => {
  it("renders TND and never a bare number", () => {
    expect(money(12.5)).toContain("TND");
    expect(money(null)).toBe("—");
  });
  it("renders units without pretending they are currency", () => {
    expect(quantity(2.5, "GB")).toBe("2.5 GB");
    expect(quantity(120, "MIN")).toBe("120 MIN");
    expect(quantity(4, "TND")).toContain("TND");
  });
  it("formats real durations", () => {
    expect(duration(258)).toBe("4m 18s");   // the value that used to be hardcoded
    expect(duration(42)).toBe("42s");
    expect(duration(null)).toBe("—");
  });
});
```

**Add** `src/lib/copy.test.ts` — the guard that stops the exact defects Cookbook 1 found from coming back:

```ts
import { describe, expect, it } from "vitest";
import { copy } from "./copy";
import { NAV } from "./nav";

describe("copy deck integrity", () => {
  it("covers all nine orb states", () => {
    for (const state of [
      "disconnected", "connecting", "preConnect", "initializing",
      "idle", "listening", "thinking", "speaking", "failed",
    ]) {
      expect(copy.assistant.state[state as keyof typeof copy.assistant.state]).toBeTruthy();
    }
  });

  it("covers all five ticket statuses (pending was missing)", () => {
    for (const status of ["open", "in_progress", "pending", "resolved", "closed"]) {
      expect(copy.labels.requestStatus[status as keyof typeof copy.labels.requestStatus]).toBeTruthy();
    }
  });

  it("declares one nav destination per route", () => {
    const count = NAV.reduce((total, group) => total + group.items.length, 0);
    expect(count).toBe(10); // the comments used to say eleven
  });
});
```

If `vitest` is not already a devDependency, adding it is a **devDependency-only** change (`vitest` + `@vitest/coverage-v8` if you want coverage). Mirror the version `Frontend/admin_dashboard` uses so both frontends run one runner — check with `node -e "console.log(require('../admin_dashboard/package.json').devDependencies.vitest)"`.

---

## 7.4 Backend gates for Cookbook 3’s new file

```sh
# Exactly what CI's lint job runs.
ruff check .
mypy packages/ services/ apps/
```

`me_reads.py` is written to pass both, provided:

* `from __future__ import annotations` is the first statement (it is);
* every function has a full signature and an explicit return type (they do);
* `Session` is imported from `sqlalchemy.orm`, not from `sqlalchemy`;
* no unused import survives — if you drop the `Payment.account_id` filter during the §3.2 preflight, remove the import too, or `ruff` fails on `F401`;
* line length matches the repo’s ruff config (check `pyproject.toml` / `ruff.toml` at the root before formatting).

An optional test, registered in `scripts/run_tests.py` so CI actually runs it:

```python
# tests for apps/business-api: customer isolation on the new client reads.
# The important assertions are negative ones:
#   * conversation_detail returns None for a session belonging to another
#     customer (so the route answers 404, not 403);
#   * no projection key is in the forbidden set below.
FORBIDDEN_KEYS = {
    "max_frustration", "sentiment", "recording_consent", "has_recording",
    "audio_record_url", "customer_vip", "last_synced_at", "failure_reason",
    "token_digest", "outcome_note", "transaction_reference",
}
```

---

## 7.5 The CI job (add this last)

Insert immediately after the existing `frontend-test` job, before `test`. It is a **copy** of the admin job with three lines changed — same node version, same cache strategy, same step order, so the two frontends fail in the same way for the same reasons.

```yaml
  # Frontend/customer_portal joins CI once the template has been replaced by real
  # implementations (cookbooks 1-6). Deliberately identical in shape to
  # frontend-test so both frontends fail the same way for the same reasons.
  # Independent of frontend-test: an admin_dashboard failure must not hide a
  # portal failure, and neither blocks the Python jobs.
  customer-portal-test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: Frontend/customer_portal
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22.12.0"
          cache: npm
          cache-dependency-path: Frontend/customer_portal/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Type check
        run: npm run typecheck
      - name: Lint
        run: npm run lint
      - name: Test
        run: npm test
      - name: Build
        run: npm run build
```

The portal has **no Dockerfile** on `version_92`, so it is correctly absent from `docker-build`, `docker-build-apps`, and `security-scan`. Do not add it to those matrices — that is precisely the mistake the `docker-build` comment records (*“listing them here built them from a non-existent file and double-pushed the same tags”*). Containerising the portal is a separate decision with its own cookbook.

### Two guardrails for the build step

1. **`npm run build` must not need secrets.** `TOKEN_SERVICE_URL` and `BUSINESS_API_URL` are read at **runtime** by server functions, never at build time (`config.ts` uses `process.env`, and `.env.example` forbids `VITE_*` for these). Verify: `npm run build` in a shell with no `.env` present must succeed. If it throws, a server-only value leaked into a client module — fix that, do not add the secret to CI.
2. **Bundle-size sanity after Cookbook 5.** LiveKit is large. Since `/assistant` is `ssr: false` and route-split, the other nine tabs must not import it. Verify after the build:

```sh
grep -rl "livekit" dist/client/assets | wc -l   # expect a small number of chunks
# and confirm no non-assistant route chunk references it
```

---

## 7.6 Static guard script (run before every push)

**Add** `Frontend/customer_portal/scripts/verify-portal.sh`:

```sh
#!/usr/bin/env bash
# Enforces the constraints from cookbooks 1-6 that a type checker cannot see.
# Run from Frontend/customer_portal.
set -uo pipefail
fail=0
check() { # name, pattern, path-glob
  if git grep -nE "$2" -- $3 >/dev/null 2>&1; then
    echo "FAIL  $1"; git grep -nE "$2" -- $3 | head -n 10; fail=1
  else
    echo "ok    $1"
  fi
}

check "no fixtures"                 "lib/fixtures"                                   "src"
check "no hardcoded hex colours"    "#[0-9a-fA-F]{3,8}"                              "src/routes src/components/portal src/components/shell"
check "no tailwind font sizes"      "text-(xs|sm|base|lg|xl|[0-9]xl)\b"              "src"
check "no tailwind radii"           "rounded-(sm|md|lg|xl|2xl|3xl)\b"                "src"
check "no arbitrary z-index"        "z-\["                                           "src"
check "no fake randomness"          "Math\.random"                                   "src"
check "no endless scroll"           "loadMore"                                       "src"
check "no raw tool names rendered"  "function_tools_executed|call_id"                "src"
check "no client-side env leak"     "VITE_(BUSINESS_API|TOKEN_SERVICE|PORTAL_SESSION)" "src .env.example"
check "no card/payment UI"          "card_number|cardNumber|cvv|expiry|Visa|Mastercard" "src"
check "no min. 8 characters"        "min\. 8|minLength=\{8\}"                        "src"

# Raw enum values must only appear inside label maps, never in a route file.
check "no raw enums in routes"      "in_progress|network_complaint|scratch_card|pre-connect-buffering" "src/routes"

exit "$fail"
```

`chmod +x` it and wire it as a `verify` script. Optionally add it as a step in the CI job — but only after it passes locally, because a red guard on day one teaches everyone to ignore it.

---

## 7.7 Manual verification matrix

Stack: postgres seeded (`alembic upgrade head`, `seed_pilot`, `seed_reference`), business-api `:8108`, token-service `:8107`, LiveKit reachable, agent-worker running, portal `:8080`. `CORS_ORIGINS` on business-api must include `http://localhost:8080` — the default is `http://localhost:5174` and will otherwise block every portal read.

### A. Authentication (Cookbook 2)

| # | Check |
|---|---|
| A1 | Client login → `/assistant`; cookie httpOnly + `SameSite=Lax`; no token in `localStorage` (`Object.keys(localStorage)` shows none) |
| A2 | Staff login → 403 with the advisor-console message, no cookie |
| A3 | Signup: 9 chars blocked client-side; 10 chars + wrong CIN → one generic message |
| A4 | 6 wrong passwords → the 15-minute lockout sentence, not a raw 429 body |
| A5 | Sign out from the account menu → `/login?notice=manual`, cookie gone |
| A6 | Expired cookie → bounced by `_portal.tsx` before any read fires (check the network tab: zero `/me/*` calls) |
| A7 | Change password → forced sign-out; old password 401s; new one works |
| A8 | Sign out everywhere from two browsers → both land on `/login` |
| A9 | Tampered cookie signature → `/login`, no crash, no stack trace in the response |

### B. Data (Cookbook 3)

| # | Check |
|---|---|
| B1 | All seven `/api/v1/me/*` routes return 200 with a client token |
| B2 | Another customer’s `session_id` → **404** (not 403, not 200) |
| B3 | Staff token and `X-API-Key` → 403 on every `/me/*` route |
| B4 | No forbidden key in any `/me/*` payload (the grep in Cookbook 3 §3.9) |
| B5 | `git diff version_92 -- .../repositories.py` empty; the `main.py` diff has no `-` lines |
| B6 | Advisor endpoints byte-identical to `version_92` with a conseiller token |
| B7 | Prepaid customer (CIN `9912`) sees balances, no invoice shell |
| B8 | Postpaid customer (`4087`, `BA-000021`) sees invoices with outstanding amounts |
| B9 | Every amount reads `TND`; every date is `Africa/Tunis` |
| B10 | A customer with no history gets `EmptyState`, never an endless skeleton |

### C. Layout (Cookbook 4)

| # | Check |
|---|---|
| C1 | 320 / 375 / 768 / 1024 / 1440 / 1920 px: no horizontal scroll, no overlap, no clipped text on all ten tabs |
| C2 | Mobile: the tabbar never covers the last row |
| C3 | Lists >10 items show bottom page indicators; no “Load more” remains |
| C4 | Page change keeps previous rows dimmed with the progress line running; no layout jump |
| C5 | Slow 3G: skeletons match the height of the rows that replace them |
| C6 | OS reduced-motion: nothing loops anywhere |
| C7 | Keyboard-only traversal of every tab; visible focus at all times; Escape closes panels |
| C8 | Lighthouse a11y ≥ 95 on `/activity`, `/billing`, `/security` |

### D. Orb and realtime (Cookbooks 5–6)

| # | Check |
|---|---|
| D1 | All nine orb states observed at least once across a full call plus one forced failure |
| D2 | Orb visually unchanged from `version_92` (screenshot diff at rest — `orb-renderer.ts` untouched) |
| D3 | Level tracks real audio; no `Math.random` in the tree |
| D4 | Tool events appear within ~1 s, in customer wording, with a tick or a neutral alert |
| D5 | Only three transcript items visible; older ones fade out |
| D6 | Customer’s real name on their turns, persona name on the agent’s |
| D7 | Mute genuinely stops publishing (the agent stops responding) |
| D8 | End, agent-initiated end, and network loss all restore the Start button |
| D9 | Summary shows a real duration — never `4m 18s` unless the call lasted 258 s |
| D10 | Two tabs → two distinct rooms, no crosstalk |
| D11 | No `TOKEN_SERVICE_URL`, LiveKit key, or token anywhere in `dist/client` |
| D12 | Arabic reply renders right-to-left |

### E. Template residue (Cookbook 1)

| # | Check |
|---|---|
| E1 | `scripts/verify-portal.sh` exits 0 |
| E2 | No credit-card, add-on, MFA, passkey, data-export, or close-account UI anywhere |
| E3 | Every button and switch either works or is gone — click every control on all ten tabs |
| E4 | `components/ui/*` contains only what is imported: `npx knip` or `depcheck`, or the import census from Cookbook 1 |
| E5 | Every `copy.ts` key is referenced: `for k in $(node -e 'ok'); do git grep -q ...; done` — unused strings mean an affordance was deleted but its promise was not |

---

## 7.8 Merge order

One branch per cookbook, merged in order, each green before the next:

1. **CB1** — deletions and honest copy. Reviewable on its own; large diff, zero risk.
2. **CB2** — auth. First user-visible improvement (sign-out exists).
3. **CB3** — backend reads + data wiring. The only backend commit in the plan.
4. **CB4** — layout. Pure presentation on top of real data.
5. **CB5** — orb + realtime. The dependency commit; needs both approval gates.
6. **CB6** — tool timeline. Small, depends on CB5.
7. **CB7** — CI. Added last so the job goes green the first time it runs.

CB2 and CB3 must not be squashed together: the backend commit needs to be revertible on its own.

---

## 7.9 Rollback matrix

| Cookbook | Revert impact |
|---|---|
| 1 | template affordances return; no data or backend effect |
| 2 | auth returns to the hardcoded-role version; cookie payload change is an **optional** field, so old and new builds read each other’s cookies |
| 3 | delete `me_reads.py`, revert the `main.py` block + one import; **no migration, no data change**; advisor surface never depended on it |
| 4 | layout only |
| 5 | two dependencies leave `package.json`; `/assistant` returns to the template. The token-service field is a defaulted optional — reverting cannot break `apps/client-widget`, which never sends it |
| 6 | tool rows fall back to neutral wording |
| 7 | remove the job; nothing else in CI referenced it |

No cookbook writes to the database, changes a migration, alters `_ROLE_RANK`, or modifies an existing backend function. The heaviest irreversible action in the entire plan is the file deletions in Cookbook 1, and those are recoverable from git.
