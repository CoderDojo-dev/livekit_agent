# Version 110 — Portal data coverage, interface language (fr/en/ar + RTL), randomised scene prompts

> **Base branch:** `version_109` (`9f8cba3`)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** **`0021_ticket_updated_at`** — alembic head moves `0020_ticket_admin_note` → `0021_ticket_updated_at`
> **Rebuild:** customer_portal web bundle; business-api image (new `me_reads` projection field)
> **Seed:** new `seed.seed_portal_activity`, wired into `make seed`, `start_dev.ps1` and `start_dev_containers.ps1`

---

## Containers & SDK

| Item                 | Change                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------- |
| New containers       | None                                                                                      |
| livekit-agents SDK   | `1.6.5` (unchanged)                                                                       |
| Backend service code | `me_reads.requests()` returns `updated_at`; `models/ticketing.Ticket` gains the column     |
| Frontend builds      | customer_portal: 24 files changed +510/−167, plus 5 new files (+1141)                      |
| alembic head         | **`0021_ticket_updated_at`**                                                              |

---

## 1. Requests and Activity: the pipeline was fine, the DATA was not

### What was actually wrong

Every endpoint the two screens read works, and had worked all along. Verified directly against the
running stack before changing anything:

- `me_reads.requests`, `.conversations`, `.conversation_detail`, `.callbacks`, `.notifications`,
  `.billing` and `.balance` all return real rows through the real projections;
- the agent's own ticket path is live end to end — `create_support_ticket` → GLPI →
  `mirror_create` → `ticketing.tickets` — and **GLPI-14 through GLPI-24 in the dev database are
  real agent-created tickets**, filed on real calls, visible to a signed-in customer;
- the HTTP handlers in `main.py` are thin passthroughs to those projections.

The problem was COVERAGE. `seed_pilot` inserts three customers with lines, invoices and balances
and stops:

| Customer            | tickets | calls | callbacks | messages | payments | top-ups |
| ------------------- | ------: | ----: | --------: | -------: | -------: | ------: |
| Amine (before)      |       7 |    79 |         9 |       16 |        5 |       0 |
| Yousra (before)     |   **0** |     4 |     **0** |    **0** |    **0** |   **0** |
| Karim (before)      |   **0** | **0** |     **0** |    **0** |    **0** |   **0** |

Sign in as two of the three pilot customers and Requests and Activity were four empty states. Even
Amine's history was monotone: every ticket `open`, so the "Resolved" tab was empty by construction,
and his callbacks carried `reason = NULL`, which the Activity list renders as a lone em dash.

### `seed_portal_activity.py` (new, 560 lines)

Gives all three customers a history that exercises every branch the screens can render: all five
ticket statuses and five categories, all four call dispositions, all three callback and
notification statuses, every payment method, and conversations with **real `conversation.turns`
rows** so the transcript, the cadence strip and the turn-density bars have something true to draw.
Subjects and transcripts are written in each customer's own language (fr / ar / en), because the
agent files a ticket in the language the call was held in.

Not mock plumbing: every row goes through the ORM into the tables the agent writes at runtime and
comes back through the same projections. Delete one and the screen loses it.

| Customer           | tickets | calls | callbacks | messages | payments | top-ups |
| ------------------ | ------: | ----: | --------: | -------: | -------: | ------: |
| Amine (after)      |      11 |    83 |        12 |       21 |        8 |       0 |
| Yousra (after)     |       3 |     7 |         2 |        4 |        0 |       7 |
| Karim (after)      |       4 |     3 |         2 |        5 |        3 |       0 |

**Idempotency bug found and fixed during verification.** The first draft guarded callbacks and
notifications on `scheduled_time` / `created_at`. Every timestamp in the file derives from one
`NOW` captured at import, so on the second run the guard matched nothing and both blocks inserted
themselves again — 21 duplicate rows, which the run-twice check caught. Guards are now on stable
identity (`(customer, reason, status)`; `(customer, channel, template, status)`), the duplicates
were removed, and three consecutive runs now report `nothing new (already seeded)`. The rule is
stated in the module docstring so the next person does not repeat it.

### Migration 0021 — `ticketing.tickets.updated_at`

A real gap, not cosmetic. The table carried `created_at` and `last_synced_at` and nothing between:
`last_synced_at` is bumped by every reconciliation pass including one that changed nothing, so no
column answered *"when did this request last actually change"*.

The portal rendered exactly that field in two places (the Requests detail panel, Activity's request
body) and `RequestItem` declared `updated_at: string | null` — but `me_reads.requests()` never
returned it, so **both screens printed an em dash forever**.

- Backfilled to `created_at`, which is true of every untouched row.
- The model carries `onupdate=func.now()`, so **every existing write path stamps it with zero
  call-site changes** — `mirror_update`, `mirror_set_status`, `mirror_resolve`, `upsert_from_glpi`.
  Proven live: mutating a ticket's status moved `updated_at` and left `last_synced_at` alone.
- New index `ix_tickets_customer_updated`.

---

## 2. Interface language — fr / en / ar with real RTL

Ported from the admin console (`lib/nexus/i18n.ts`) rather than reinvented, so the two front ends
behave identically.

- **`lib/i18n.ts`** — three locales, English as the compile-time source of truth for the key set,
  per-key fallback so an incomplete dictionary degrades one string at a time and can never render a
  raw key at a customer.
- **`lib/nav.ts` rewritten to carry keys.** The ten destinations, their three section headings and
  every page title/subtitle now resolve through `t()` — the language control reaches the
  navigation, not only the chrome around it.
- **`LanguageToggle`** in the top bar, beside the theme toggle, and the same control under
  Preferences → Language. A menu, not a cycling button: with three languages a cycle makes
  reaching the one you want a guessing game and never shows which is current. Each option is
  written in its own script, which is the one label a speaker of that language always recognises.
- **RTL is real, not a `lang` attribute.** Arabic sets `dir="rtl"`, and the shell's physical
  properties were converted to logical ones: the rail (`start-0`, `border-e`), the main column's
  inset (`lg:ps-64` — with `pl-*` the 256px gap landed on the wrong side and content ran under the
  rail), the detail sheet, both dropdowns, the switch thumb, the segmented dividers, the tab-count
  and the tabbar badge. Verified in the browser: `ps/start/border-s` all swap side under `dir=rtl`.
- **Set before first paint.** `lang` and `dir` are written by the boot script from localStorage,
  because applying direction from the bundle would paint one frame of a left-to-right Arabic page
  and then flip the whole layout.

**The two language settings are deliberately kept apart.** `preferences.agentLanguage` writes
`crm.customers.preferred_language` and decides what the ASSISTANT SPEAKS; this one is presentation
only and decides what the SCREEN SAYS. They are rendered one above the other under Preferences →
Language, each with a sentence saying what it does not change — a customer who reads French but
wants to be spoken to in Arabic is an ordinary case in Tunisia, not an edge one.

**Scope, stated honestly:** this translates the shell — navigation, page heads, both menus, and the
repeated vocabulary. Page body copy in `lib/copy.ts` stays English for now and falls back per key.

---

## 3. Assistant scene: prompts land somewhere new every time

The four chips sat at four hard-coded corners, which after the second rotation reads as four signs
bolted to the page rather than as things drifting through it. Every appearance now picks a fresh
spot — random, but never *anywhere*:

1. **The orb is sacred.** Chips are confined to the two outer bands, addressed with logical
   `start`/`end` insets so the scene mirrors in Arabic.
2. **No two chips can collide.** Rather than rejection-sampling and hoping, each slot owns one
   band-half and randomises only within it — overlap is impossible by construction, not by luck.
3. **The two sides never line up.** End-side bands are offset downward from start-side ones.

**Verified by simulation: 200,000 draws × 4 chips = 800,000 placements — 0 intersecting the 446px
stage region, 0 chip-on-chip overlaps, 0 leaving the scene box.**

The entrance is unchanged and shared by all four, as asked: rise 6px out of a 4px blur over 420ms,
leave the same way, one slot every 2600ms. The one structural change is that **the positioned
element is now the element `AnimatePresence` keys on** — keying an inner span inside a positioned
wrapper would drag the departing chip across the screen to the new coordinates before it finished
fading, which is the one motion this scene must never make.

---

## 4. The mark is now a person

`BrandMark` was an angular "N" left from the pre-rebrand release: it said nothing about the product
and said it in a letter the product is no longer named after. This is a self-care portal — the
whole surface is one customer's own account — so the mark is the customer. Drawn rather than
imported from lucide so it inherits `currentColor`, with a small head and wide shallow shoulders
that stay legible at 18px where a stock `User` closes its shoulder arc into a smudge. Both favicons
were redrawn to match.

---

## Validation

**Frontend**

- `npx tsc --noEmit` → clean.
- `npx eslint src` → 0 errors, 1 warning (`react-refresh/only-export-components` on `data.tsx`, pre-existing).
- `npx vitest run` → **10 files, 93 tests passing** (was 70 at version_108). New: 15 i18n tests, 8 preference/RTL tests.
- `npm run build` → exit 0.

**Backend**

- `pytest apps/business-api/tests` → **215 passed**.
- `pytest packages/persistence/tests mcp-servers/ticketing-glpi` → **5 passed**.
- `pytest tests` → **16 passed**.
- `alembic upgrade head` → applied; single head `0021_ticket_updated_at`; backfill confirmed 21/21 rows.
- Seed run three times consecutively → `nothing new (already seeded)` each time.

**Live HTTP end-to-end.** A portal session was minted server-side through `portal_auth.open_session`
(which takes an account object — no password was entered or guessed anywhere) and revoked
afterwards. All six `/api/v1/me/*` endpoints returned **HTTP 200** with the seeded data, including
`updated_at` distinct from `created_at` on all four tickets and the three payments the Billing
screen renders.

**Browser.** Boot script verified to set `lang="ar"` / `dir="rtl"` before paint; the logical
utilities (`ps-*`, `start-*`, `border-s`, `ms-*`) confirmed to swap side under `dir=rtl`; new
favicons served.

### Note for whoever deploys this

The migration and the new `me_reads` field were applied to the running dev stack with `docker cp` +
`alembic upgrade head`, which lives in the container's writable layer. **A `make rebuild` (or any
container recreate) is needed to bake them into the image** — the source changes are all in the
repo, so the rebuild is the only step.
