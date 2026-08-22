# Version 109 — Client portal: motion layer, icon language, assistant scene backdrop

> **Base branch:** `version_108` (`6e5f579`)
> **New containers:** None
> **livekit-agents SDK:** 1.6.5 (no bump)
> **Migration:** none (head stays `0020_ticket_admin_note`)
> **Rebuild:** customer_portal web bundle
> **Backend:** untouched — every figure added to a screen in this version was already in a payload the portal was fetching and discarding.

---

## Containers & SDK

| Item                 | Change                                                                          |
| -------------------- | ------------------------------------------------------------------------------- |
| New containers       | None                                                                              |
| livekit-agents SDK   | `1.6.5` (unchanged)                                                               |
| Backend service code | none (frontend-only version)                                                      |
| Frontend builds      | customer_portal: 17 files changed +1841/−548; 3 new components                    |
| alembic head         | `0020_ticket_admin_note` (unchanged)                                              |

---

## Why

The portal was correct and inert. It had the admin dashboard's tokens but almost none of its
behaviour: cards did not answer the cursor, sections did not assemble, six of the ten screens had
no icon on them at all, and three screens carried a headline number in a card that was two thirds
empty because the facts that qualified it were being thrown away.

Three defects underneath that, all of them silent:

- **`.portal-section` did not exist.** `data.tsx` put the class on every `PageSection` and
  `help.tsx` put it on all five of its topic tiles. It was defined in no stylesheet, so it did
  nothing anywhere.
- **`t-body-l` did not exist.** Help's topic titles asked for it and rendered at the inherited
  size instead — which is why Help was the flattest screen in the product.
- **The notification tray did not close.** No outside-click handler, no Escape, no `aria-expanded`
  — six lines below an `AccountMenu` in the same file that has always had all three.

---

## The design system (`styles.css`, +266)

A third volume, strictly additive — no existing token or rule was changed, and every value added
is still achromatic (`R === G === B`).

| Addition                     | What it does                                                                                                |
| ---------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `t-body-l` (15/24)           | The nineteenth type token. Between `t-body` and `t-title-3`: the size for a line that leads a card.           |
| `.portal-section`            | Now real. Owns the staggered page entrance, driven by `--rise-delay`, capped at four steps (240 ms).          |
| `card-lift`                  | Border + shadow + a 2 px lift. Opt-in, so only a card that *is* a target lifts.                               |
| `row-accent`                 | A row cannot lift without tearing the hairline above it, so it grows the rail's 2 px leading stroke instead.   |
| `.live-dot`                  | The one infinite animation outside the assistant scene, for states that genuinely are in motion.               |
| `.scene-*` (4 layers)        | The assistant backdrop: grid, aurora, scan, float. See below.                                                 |
| `--grid-line`, `--aurora-ink`, `--sheen` | New tokens, defined for both themes. Verified in the browser: dark `#ffffff0d`, light `#0000000e`. |

Every animation added is neutralised by the two existing reduced-motion blocks, which match on `*`.

---

## The assistant scene (`scene-backdrop.tsx`, new)

The one screen with nothing in the middle of it: an orb, a sentence, a button, and a great deal of
empty page. Five layers, all decorative, all `pointer-events-none` and `aria-hidden`, painted at
z-0 under a stage the route lifts to z-10. **No existing assistant component was modified** — the
orb, the controls, the live stream and the session provider are byte-identical.

1. **Brackets** — four corner rules, so the field reads as a drawing with edges.
2. **Grid** — 64 px hairlines drifting exactly one cell per 24 s, radially masked (an unmasked grid
   runs into the topbar and the rail and reads as a rendering bug).
3. **Aurora** — one achromatic light breathing on a 20 s cycle where the orb sits.
4. **Scan** — a single hairline crossing the field every 11 s. Noticed about once per visit.
5. **Prompts** — the only layer that means anything: four slots holding things the assistant can
   *actually* do ("Ask a question", "Report a problem", "Explain my bill", …), rotating round-robin
   so one chip changes at a time. It answers "what am I allowed to say?" before the customer has to
   ask. Every entry is a subset of `copy.about.can`, never a wish list.

**The call is the subject.** Starting a conversation drops the whole backdrop to 28 % and removes
the prompts entirely — during a call the transcript is what is being read.

Measured at 1280×720: the four chips clear the 446 px central stage region completely, nearest edge
250 px away. Below `md` the prompts do not render at all (the orb is 320 px at rest, a phone column
is 375 px wide — there is no outer margin left to put a chip in); the grid, aurora and scan still run.
Under reduced motion the rotation timer is never started, so the four opening prompts hold.

---

## Per-tab

### Assistant

Backdrop mounted; a third assurance chip ("Never recorded") — already true of the worker and the one
thing the scene never said.

### Billing — the largest content gain

`/me/billing` has returned a `payments` array since the endpoint was written and **no screen has
ever rendered it**, so "did my payment go through?" had no answer anywhere in the portal.

- New **Payments** section: amount, method (glyph per `card` / `bank_transfer` / `wallet` / `voucher` / `cash`), invoice, status, date.
- The headline card was one tile with two thirds of a card of empty space beside it. Now three:
  amount due, next due, last settled payment — all three already in the payload.
- Invoice panel gains a settled-vs-total bar drawn from the two numbers on the row above it.
- `lastSettled()` filters to `succeeded` — a pending capture is not "what you last paid".

### Services

Balance glyphs per type; **top-up status was rendering the raw OCS enum** (`completed`, lowercase)
next to five labels that had all been translated — now `copy.labels.rechargeStatus`. Channel glyphs
make the top-up column scannable. "Expiring soon" chip, derived from the `expires_on` already printed
beside it. Plan names dropped from `t-metric-l` (26 px, the size reserved for a headline figure) to
`t-title-2` — a plan is called "Smart 40", not 26 point.

### Help — rewritten

Five bare links carrying two classes that did not exist became five real cards. **Six-question FAQ
added**: the page previously had no answers on it at all, so a customer with a question had to leave
Help to find out whether Help could help. Every answer restates a guarantee the product already
makes elsewhere.

### Requests

Category glyphs; the row was four cells in a line with three monospaced greys competing with the one
line that says what the request is — the subject now leads. Priority surfaced on the hero (it was in
the payload but only visible after opening the panel). Timeline became a rail. **Fixed mojibake:** a
`—` had been round-tripped through the wrong encoding and printed three Latin-1 characters into the
panel; the file's BOM is also gone.

### Activity

Transcript turns now read by shape — the assistant speaks from a raised surface behind a leading
rule, you speak in plain ink. Callback rows had "Scheduled" in bold on every row and the reason
buried in the caption; swapped. Notification rows had the channel as the headline and the message as
the caption; swapped.

### Profile / Preferences / Security

Three hand-written copies of the same section nav, already drifted (Profile used `t-label` in a strip
that never became a column). One `SettingsNav` with icons. Profile gains a clipboard control on the
customer reference — the one string a customer is ever asked to read out — and the sessions pointer
became a real target instead of a caption-sized text link.

### About

Masthead dropped from `t-display` (40 px) to `t-title-1`: a sentence about the product, not a
headline number. Can/cannot lists moved into cards — the single most reassuring content in the portal
was sitting on the page background at caption level.

### Shell

`NotificationTray` extracted and fixed (outside-click, Escape, `aria-expanded`, `role="dialog"`,
cross-fade, "see every message" → Activity). **Deliberately no unread badge**: the endpoint returns a
*delivery* state (queued/sent/failed) and has no concept of whether the customer has looked at a
message — a dot on the bell would be a claim the data cannot support. Topbar gains the destination's
own glyph, keyed off the same `lib/nav.ts` strings the rail uses. Mobile tabbar gains an active rule.

---

## Validation

- `npx tsc --noEmit` → clean.
- `npx eslint src` → 0 errors, 1 warning (`react-refresh/only-export-components` on `data.tsx`, pre-existing — verified against the stashed HEAD version).
- `npx vitest run` → **9 files, 70 tests, all passing.**
- `npm run build` → clean (client + SSR + nitro).
- Browser-verified against the running dev server on `:8080`: all five new utilities compile into the
  served stylesheet, all four scene animations resolve to their keyframes, and both themes' new tokens
  are achromatic.
