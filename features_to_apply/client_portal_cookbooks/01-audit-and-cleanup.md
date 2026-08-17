# COOKBOOK 1 — FULL AUDIT AND CLEANUP

**Backend touched:** none. **New dependencies:** none. **Risk:** low, fully reversible.
**Goal:** the portal stops lying. Every affordance that no `version_92` backend concept can honour is deleted, every duplicated source of truth is collapsed, and the four off-design screens are brought back inside the design system.

---

## 1.1 Wiring map — verified on `version_92`

`REAL` = reads business-api · `FIXTURE` = imports `@/lib/fixtures/*` · `LOCAL` = React state only · `STATIC` = copy deck only.

| # | Route | File | Data today | Verdict | Cookbook that fixes it |
|---|---|---|---|---|---|
| 1 | `/assistant` | `routes/_portal/assistant.tsx` | `interactions[0].transcript` replayed by a `setTimeout` ladder; `level` = `0.25 + Math.random()*0.65`; summary hardcodes `"4m 18s"` and `"2"`; composer `<input>`, Volume and Keyboard buttons have **no handler** | FIXTURE — scripted fake call | 5 + 6 |
| 2 | `/activity` | `activity.tsx` | `interactions` fixture | FIXTURE | 3 + 4 |
| 3 | `/requests` | `requests.tsx` | `requests` fixture | FIXTURE | 3 + 4 |
| 4 | `/services` | `services.tsx` | `plan`, `usage`, `addons`, `available` fixtures | FIXTURE | 3 + 4 |
| 5 | `/billing` | `billing.tsx` | `invoices`, `nextCharge`, `paymentMethod`, `spend` fixtures (GBP) | FIXTURE | 3 + 4 |
| 6 | `/help` | `help.tsx` | `topics`, `popular` fixtures | FIXTURE | 1 (static) |
| 7 | `/profile` | `profile.tsx` | `fetchProfileDetail()` → `GET /api/v1/me/profile/detail` | **REAL — the reference implementation** | keep |
| 8 | `/preferences` | `preferences.tsx` | 15 `useState` hooks, notification matrix seeded by `(ri + ci) % 3 !== 2` | LOCAL — persists nothing | 1 + 4 |
| 9 | `/security` | `security.tsx` | `sessions`, `securityEvents` fixtures + hardcoded `"Last changed 12 March"`, `"Not turned on"`, `"No passkeys yet"` | FIXTURE, and two real endpoints never called | 2 + 3 |
| 10 | `/about` | `about.tsx` | `copy.about.*` | STATIC — correct | keep (one sentence fix) |
| — | topbar | `components/shell/portal-topbar.tsx` | name/initials REAL via `fetchProfileDetail`; tray from `notifications` fixture with an `unread` flag; account `<button>` has **no `onClick`** | MIXED | 2 + 3 |

`routes/index.tsx` is five lines and redirects `/` → `/assistant`, so the first thing a customer sees is the scripted demo.

---

## 1.2 Defect register (each line re-verified on `version_92`)

| ID | Defect | Evidence | Severity | Fixed in |
|---|---|---|---|---|
| D‑1 | Signup enforces 8 characters, the backend enforces 10 → guaranteed 400 | `signup.tsx` `minLength={8}` ×2 and the label “Password (min. 8 characters)” vs `portal_auth.MIN_PASSWORD_LENGTH = 10`, mapped to 400 by `_AUTH_STATUS["weak_password"]` | HIGH | 2 |
| D‑2 | A staff account can sign into the portal and land in a permanent 403 shell | `auth.server.ts` `login()` hardcodes `role: "client"` and ignores the backend’s `role`/`kind`; `LoginResponse` does not declare `customer_id` although the backend returns it | HIGH | 2 |
| D‑3 | There is no way to sign out | `logout()` exists and is exported; `copy.shell.signOut` exists; `portal-topbar.tsx` renders a bare `<button>` with no `onClick`; no `/logout` route | HIGH | 2 |
| D‑4 | `Me.kind` is a type lie | `me.server.ts` declares `kind: "staff" \| "customer"`; `Principal.kind` is `"staff" \| "client" \| "service"` and `signup_client` writes `kind="client"` | LOW | 2 |
| D‑5 | A currency string is hardcoded inside a shared primitive | `primitives.tsx` → `Meter`: “Over your monthly allowance. Extra blocks are billed at £6.00 each.” | MEDIUM | 1 |
| D‑6 | Two navigation sources of truth | `portal-rail.tsx` renders `NAV`; `portal-tabbar.tsx` renders its own hardcoded 5-item `ITEMS` array | MEDIUM | 1 |
| D‑7 | “Onze destinations” repeated where there are ten | `lib/nav.ts` header comment, `portal-rail.tsx` doc comment | LOW | 1 |
| D‑8 | Root 404 / error screens use shadcn tokens, not portal tokens | `__root.tsx`: `bg-background`, `text-foreground`, `text-muted-foreground`, `bg-primary`, `rounded-md`, `text-7xl`, `border-input`, `hover:bg-accent`; head advertises `twitter:site "@Lovable"` | MEDIUM | 1 |
| D‑9 | Unread dot that nothing can compute | `portal-topbar.tsx` `notifications.filter(n => n.unread)`; `billing.notifications` has **no** read/unread column | MEDIUM | 3 |
| D‑10 | `--z-callbar: 40` exists with no call-bar component | `styles.css` | INFO | 5 uses it |
| D‑11 | `caret` keyframe declared and never used | `styles.css` | INFO | 5 uses it |
| D‑12 | Portal is English-only while `preferred_language` allows `fr\|ar\|en` and the demo customer is `ar` | `crm.customers` CHECK + `profile.tsx` `LOCALES` | MEDIUM | deferred (see §1.7) |

---

## 1.3 Delete list — affordances with no `version_92` backend concept

**Rule: delete, do not disable.** A greyed-out “Close your account” is still a promise. Remove the orphaned `copy.ts` keys in the same commit.

| File | Remove | Why (verified) |
|---|---|---|
| `_portal/security.tsx` | the whole `copy.security.callout` card + the `twoStep` `FieldRow` | no MFA column, no TOTP route anywhere |
| `_portal/security.tsx` | the `passkeys` `FieldRow` + `copy.security.addPasskey` | no WebAuthn anywhere |
| `_portal/security.tsx` | the entire `data` section: all three `copy.security.blocks` + `copy.security.irreversible` + the `data` nav entry | no export, no transcript-delete, no account-close endpoint; one of them is destructive |
| `_portal/preferences.tsx` | notification matrix (`copy.preferences.channels` × `copy.preferences.events`) | no delivery-preference storage; the seed is a `(ri+ci)%3` checkerboard |
| `_portal/preferences.tsx` | `confirm`, `remember`, `proactive` switches + `copy.preferences.confirmDialog` | they promise agent behaviour the portal has no authority to set |
| `_portal/preferences.tsx` | `pushToTalk`, `noise`, `echo` switches | no browser audio pipeline until Cookbook 5; even then these are LiveKit publish options, not stored preferences |
| `_portal/preferences.tsx` | `assistantVoice`, `speakingPace`, `responseLength`, `retention` (+ their copy keys) | no storage, no effect; `retention` also makes `copy.about.dataBody` false |
| `_portal/billing.tsx` | “PAYMENT METHOD” card, `copy.billing.update`, `copy.billing.retry`, `copy.billing.providerNote` | no card-on-file column anywhere in `billing.*`; no payment-provider integration |
| `_portal/billing.tsx` | `copy.billing.downloadAll`, `copy.billing.pdf` | no invoice-document endpoint |
| `_portal/services.tsx` | “ADD-ONS”, “AVAILABLE TO ADD”, `copy.services.compare`, `manage`, `add` | no add-on entity; no client-reachable plan-change route |
| `_portal/requests.tsx` | `copy.requests.create`, `reply`, `replyPlaceholder`, `send` | writes; creating a ticket from the portal is a new feature, not access to an existing one |
| `_portal/help.tsx` | `copy.help.search` field and `copy.help.articles(n)` counts | no client-facing knowledge route among the shipped routes |
| `_portal/assistant.tsx` | composer `<input>`, Volume `IconButton`, Keyboard `IconButton`, the hardcoded `"4m 18s"` / `"2"` summary values | verified: no handlers, invented numbers (Cookbook 5 rebuilds this screen) |
| `portal-topbar.tsx` | the `Search` `IconButton` (no handler) | a search box that does nothing is worse than none |
| `_portal/activity.tsx` | the `callbacks` filter tab **or** wire it | Cookbook 3 ships `GET /api/v1/me/callbacks`, so prefer wiring; delete only if you skip that endpoint |

### Fixture deletion order (hard rule)

A fixture may only be deleted **in the same commit that lands its replacement**:

1. `help.ts` → folded into `copy.ts` (this cookbook).
2. `customer.ts` (`sessions`, `securityEvents`, `notifications`) → Cookbook 3 (`/me/sessions`, `/me/notifications`).
3. `requests.ts` → Cookbook 3 (`/me/requests`).
4. `billing.ts`, `services.ts` → Cookbook 3 (`/me/billing`, `/me/balance`, `/me/profile`).
5. `interactions.ts` → **last**, because it feeds both `/activity` and the `SCRIPT` in `/assistant`; it goes when Cookbook 5 lands.

Final gate: `git grep -n "lib/fixtures" -- Frontend/customer_portal/src` returns nothing.

### The 46 `components/ui/*` files

Run gate 2 from `00-INDEX-AND-GROUND-TRUTH.md §5`. If it prints nothing, delete `src/components/ui/` in one forward commit, plus `src/hooks/use-mobile.tsx` **only if** `ui/sidebar.tsx` was its only consumer. **Do not touch `package.json`, either lockfile, `vite.config.ts`, `tsconfig.json`, `eslint.config.js`, `.prettierrc`, or `components.json`** — unused dependencies are harmless, a manifest edit is not. This project is Lovable-connected (`AGENTS.md`): forward commits only, never force-push, never rebase.

---

## 1.4 Code — the five cleanup edits

### 1.4.1 `Meter` currency string leaves the design system (D‑5)

**Modify** `src/components/portal/primitives.tsx` — the *only* sanctioned edit to this file, zero visual change:

```diff
 export function Meter({
   label,
   used,
   limit,
   unit,
+  overNote,
 }: {
   label: string;
   used: number;
   limit: number;
   unit: string;
+  /** Sentence shown when usage exceeds the allowance. Lives in copy.ts, never here. */
+  overNote?: string;
 }) {
@@
-      {over ? (
+      {over && overNote ? (
         <div className="t-caption mt-sp-3 text-ink-3">
-          Over your monthly allowance. Extra blocks are billed at £6.00 each.
+          {overNote}
         </div>
       ) : null}
```

**Modify** `src/lib/copy.ts` — add to the `services` block:

```ts
  services: {
    plan: "YOUR PLAN",
    // ...existing keys that survive §1.3...
    usage: "USAGE",
    overAllowance: "You are over your monthly allowance.",
    renews: (date: string) => `Renews on ${date}`,
    activeSince: (date: string) => `Active since ${date}`,
  },
```

### 1.4.2 One navigation source of truth (D‑6)

**Replace** `src/components/shell/portal-tabbar.tsx` entirely — same five destinations, same markup, derived from `NAV`:

```tsx
import { Link, useRouterState } from "@tanstack/react-router";
import {
  AudioLines,
  History,
  Inbox,
  Layers2,
  ReceiptText,
  Info,
  type LucideIcon,
} from "lucide-react";
import { NAV } from "@/lib/nav";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  "audio-lines": AudioLines,
  history: History,
  inbox: Inbox,
  "layers-2": Layers2,
  "receipt-text": ReceiptText,
};

/** 11.9 — en dessous de lg, le rail devient une barre basse de cinq entrees.
 *  Une seule source de verite : NAV. Renommer ou retirer une destination ne
 *  peut plus laisser un lien mort ici. */
const MOBILE_HREFS = [
  "/assistant",
  "/activity",
  "/requests",
  "/services",
  "/billing",
] as const;

const ITEMS = MOBILE_HREFS.map((href) => {
  const item = NAV.flatMap((group) => group.items).find((i) => i.href === href);
  return item ?? null;
}).filter((item): item is NonNullable<typeof item> => item !== null);

export function PortalTabbar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <nav
      aria-label="Portal"
      className="fixed inset-x-0 bottom-0 z-20 flex h-14 border-t border-stroke-subtle bg-surface-1 lg:hidden"
    >
      {ITEMS.map((item) => {
        const Icon = ICONS[item.icon] ?? Info;
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            to={item.href}
            className={cn(
              "flex flex-1 flex-col items-center justify-center gap-sp-2 transition-colors duration-200",
              active ? "text-ink-1" : "text-ink-5",
            )}
          >
            <Icon size={17} strokeWidth={1.5} />
            <span className="t-micro-2">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
```

### 1.4.3 Stale destination count (D‑7)

**Modify** `src/lib/nav.ts` header:

```diff
-/**
- * lib/nav.ts — les onze destinations, chapitre 11.2.
- * Aucune douzieme destination.
- */
+/**
+ * lib/nav.ts — les dix destinations, chapitre 11.2 (3 + 3 + 4).
+ * Source unique : le rail, la barre mobile et PAGE_HEAD derivent d'ici.
+ * Aucune onzieme destination.
+ */
```

**Modify** `src/components/shell/portal-rail.tsx` doc comment:

```diff
-/**
- * components/shell/portal-rail.tsx — chapitre 11.
- * Onze destinations, trois groupes, un pied de marque.
- */
+/**
+ * components/shell/portal-rail.tsx — chapitre 11.
+ * Dix destinations, trois groupes, un pied de marque.
+ */
```

If `/preferences` is folded into `/profile` later, update both comments again to nine rather than leaving a second stale count.

### 1.4.4 Root 404 + error screens rejoin the design system (D‑8)

**Modify** `src/routes/__root.tsx` — replace both components; keep `reportLovableError`, keep `<Outlet />`, keep the font links:

```tsx
import { Button, Card } from "@/components/portal/primitives";
import { copy } from "@/lib/copy";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px] text-center">
        <div className="t-mono-l text-ink-4">404</div>
        <h1 className="t-title-2 mt-sp-5 text-ink-1">{copy.errors.notFoundTitle}</h1>
        <p className="t-body mt-sp-3 text-ink-4">{copy.errors.notFoundBody}</p>
        <div className="mt-sp-8">
          <Link to="/">
            <Button variant="primary">{copy.errors.goHome}</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-0 px-sp-8">
      <Card className="w-full max-w-[420px] text-center">
        <h1 className="t-title-2 text-ink-1">{copy.errors.brokenTitle}</h1>
        <p className="t-body mt-sp-3 text-ink-4">{copy.errors.brokenBody}</p>
        <div className="mt-sp-8 flex justify-center gap-sp-4">
          <Button
            variant="primary"
            onClick={() => {
              router.invalidate();
              reset();
            }}
          >
            {copy.common.tryAgain}
          </Button>
          <a href="/">
            <Button variant="quiet">{copy.errors.goHome}</Button>
          </a>
        </div>
      </Card>
    </div>
  );
}
```

Also in the same file, replace the borrowed social handle:

```diff
-      { name: "twitter:site", content: "@Lovable" },
+      { name: "twitter:site", content: "@Nexus" },
```

**Modify** `src/lib/copy.ts` — add the `errors` block (new strings must never be inline):

```ts
  errors: {
    notFoundTitle: "We could not find that page",
    notFoundBody: "The page may have moved, or the link may be out of date.",
    brokenTitle: "This page did not load",
    brokenBody: "Something went wrong on our side. Try again, or go back to the start.",
    goHome: "Go to the assistant",
    signedOut: "You have been signed out.",
    sessionExpired: "Your session has expired. Sign in again.",
  },
```

### 1.4.5 `/help` becomes honest static content, `/about` stops lying

**Modify** `src/lib/copy.ts` — move the curated topics out of `lib/fixtures/help.ts` (open that file and copy the *text* only; do not invent topics):

```ts
  help: {
    browse: "BROWSE BY TOPIC",
    contactLabel: "STILL NEED HELP?",
    contactBody:
      "The assistant can answer most questions instantly, and hand you to a specialist when it cannot.",
    startConversation: "Start a conversation",
    askInstead: "Ask the assistant instead",
    // Curated, static, and true: transcribed from lib/fixtures/help.ts at cleanup time.
    topics: [
      { title: "Billing and payments", body: "Invoices, balances, and what a charge means." },
      { title: "Your plan", body: "What you have today and how it renews." },
      { title: "Network and coverage", body: "Slow data, no signal, and known incidents." },
      { title: "SIM and device", body: "Blocked SIM, replacement, and activation." },
      { title: "Your account", body: "Contact details, language, and security." },
    ],
  },
```

> The five topic titles above must be reconciled against `lib/fixtures/help.ts` when you open it. If the fixture holds different titles, keep the fixture’s wording — it was written for this design — and only drop the fake `articles(n)` counts and the search field.

**Modify** `copy.about.dataBody` — the retention control is being deleted, so the sentence about it becomes false:

```diff
-    dataBody:
-      "Your voice is never stored as audio. Transcripts are kept for as long as you choose in Preferences, and you can delete them at any time. Nothing you say is used to train anyone else's assistant.",
+    dataBody:
+      "Your voice is never stored as audio. A masked, written record of each conversation is kept so you and our advisors can refer back to it. Nothing you say is used to train anyone else's assistant.",
```

> Justification, verified: `conversation.turns.transcript_masked` is what the platform persists (PII-masked by `pii-shield`), `call_sessions.audio_record_url` is nullable and unused by the portal, and there is no customer-controlled retention setting anywhere in the schema.

Also review `copy.about.cannot`, which lists “Change your password” — true of the *assistant*, and still true after Cookbook 2 gives the *portal* that ability. No change needed, but do not add a claim that the assistant can do it.

---

## 1.5 `/preferences` — the honest version (no backend)

Keep only genuinely client-side presentation settings, persisted in `localStorage`:

| Keep | Mechanism |
|---|---|
| `reduceMotion` | adds `data-reduce-motion="true"` on `<html>`; `styles.css` already collapses animation under `prefers-reduced-motion`, so add one CSS rule mirroring it for the manual toggle |
| `density` (`Comfortable` / `Compact`) | `data-density` on `<html>`; Cookbook 4 reads it for section padding |
| `textSize` (`Default` / `Large`) | `data-text-size` on `<html>` |
| `captions` | default for the transcript panel in Cookbook 5 |

**Add** `src/lib/preferences.ts`:

```ts
/**
 * lib/preferences.ts — presentation settings only.
 *
 * Nothing here is sent to a server, because no preferences table exists in
 * version_92 and inventing one would change backend behaviour. Every value is
 * a pure rendering choice applied as a data-attribute on <html>.
 */
export type Density = "comfortable" | "compact";
export type TextSize = "default" | "large";

export type PortalPreferences = {
  reduceMotion: boolean;
  density: Density;
  textSize: TextSize;
  captions: boolean;
};

export const DEFAULT_PREFERENCES: PortalPreferences = {
  reduceMotion: false,
  density: "comfortable",
  textSize: "default",
  captions: true,
};

const KEY = "nexus_portal_preferences";

export function readPreferences(): PortalPreferences {
  if (typeof window === "undefined") return DEFAULT_PREFERENCES;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<PortalPreferences>) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: PortalPreferences): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage disabled — the session-scoped value still applies */
  }
  applyPreferences(next);
}

/** Single place that touches the document. Attributes only, never inline styles. */
export function applyPreferences(next: PortalPreferences): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset["reduceMotion"] = String(next.reduceMotion);
  root.dataset["density"] = next.density;
  root.dataset["textSize"] = next.textSize;
}
```

**Modify** `src/styles.css` — append at the end, mirroring the existing reduced-motion block exactly (same values, no new tokens):

```css
/* Manual mirror of the OS-level preference above, driven by lib/preferences.ts. */
[data-reduce-motion="true"] *,
[data-reduce-motion="true"] *::before,
[data-reduce-motion="true"] *::after {
  animation-duration: 0.001ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.001ms !important;
}

/* Compact density: one step down the existing spacing scale. No new values. */
[data-density="compact"] .portal-section {
  padding-block: var(--sp-6);
}

[data-text-size="large"] {
  font-size: 15px;
}
```

**Known limitation, documented rather than hacked:** `orb.tsx` reads `matchMedia("(prefers-reduced-motion: reduce)")` **once**, in a `useEffect` with an empty dependency array, and passes the result into `createOrbRenderer`. A runtime toggle therefore does **not** re-initialise the renderer. The orb honours the OS setting only. Do not rewrite the renderer to chase this; state it in `copy.preferences` instead:

```ts
    reduceMotionNote:
      "Applies across the portal immediately. The assistant visual follows your system setting.",
```

If you would rather not ship a three-control tab, the alternative is to fold these into `/profile` as an “Appearance” section and drop `/preferences` from `NAV` — then `PAGE_HEAD`, both nav comments, and the tabbar list must be updated in the same commit.

---

## 1.6 Concrete implementation list produced by this audit

| Item | Cookbook | Backend |
|---|---|---|
| Sign-out wired in the topbar | 2 | none |
| Password min length 10, non-client login refused, `Me.kind` fixed, 429 surfaced | 2 | none |
| Change password + sign out of all other devices | 2 | none (routes exist) |
| Active sessions list + “last changed” | 3 | `GET /api/v1/me/sessions` |
| Activity = real conversations + transcript | 3 | `GET /api/v1/me/conversations`, `/{session_id}` |
| Requests = real tickets (read-only) | 3 | `GET /api/v1/me/requests`, `/{glpi_ticket_id}` |
| Billing = postpaid invoices **and** prepaid balance | 3 | `GET /api/v1/me/billing`, `/me/balance` |
| Services plan section | 3 | none — `/api/v1/me/profile` already carries it |
| Notification tray | 3 | `GET /api/v1/me/notifications` |
| Callbacks | 3 | `GET /api/v1/me/callbacks` |
| Pagination, skeletons, progress, section rhythm, motion | 4 | none |
| Orb driven by a real LiveKit session | 5 | token-service optional additive field |
| Tool/persona event timeline | 6 | none |
| Typecheck / lint / build / CI | 7 | none |
| Delete 46 shadcn files, 6 fixtures, and every unbacked affordance | 1 → 5 | none |

---

## 1.7 Deferred, recorded, not attempted

* **Arabic + RTL (D‑12).** `crm.customers.preferred_language` allows `fr|ar|en`, `me_profile_detail` returns it, `profile.tsx` displays it — but `copy.ts` is a single English deck with no i18n layer and no RTL handling. Full i18n is a feature, not a cleanup. Until it is scoped: do not add copy claiming the portal honours the language setting. Note that `live-turn` text in Cookbook 5/6 uses `dir="auto"`, exactly as the client-widget does, so Arabic transcript text renders correctly even in the English shell.
* **Portal writes** (create a ticket, reply to a ticket, book a callback). New features, not access to existing ones. Out of scope for Cookbooks 1–7.
* **Client-facing knowledge search.** Would require a new cross-service path from the portal to the knowledge service. French-only corpus stands (your decision 5).
* **`tsconfig.tsbuildinfo`** is tracked in git. Noted only; `.gitignore` is frozen.
