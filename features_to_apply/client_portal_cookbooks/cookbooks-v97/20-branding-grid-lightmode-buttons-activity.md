# Cookbook 20 - Branding, premium grid, light mode, button refinement, activity micro-metric

Base: `version_96` @ `fa220abc85ed498bc83e158d6596d4510b87441f`.
Covers brief sections 13, 14, 15, 16 and 9. These are grouped because they all land in the token layer (`styles.css`), the centralised copy layer (`copy.ts`), or `primitives.tsx` / `data.tsx` - and because doing them separately would mean touching the same three files four times.

Order matters: branding first (it renames a storage key that light mode then uses), then the grid, then light mode (which must re-theme the grid), then buttons, then the activity metric.

---

## 20.0 Design-system constraints that bind everything below

Read this before writing a line. `styles.css` is titled "THE MONOCHROME EXPERIENCE BIBLE" and the constraints are real, not stylistic preference:

1. **Strictly achromatic.** Every one of the 13 greys satisfies R === G === B. `--n-0: #000000` through `--n-12: #ffffff`. There is not one hue in the entire palette. Light mode must therefore be greys only - no blue-tinted surfaces, no warm off-white.
2. **Radius ceiling is 12px** (`--r-5`). There are no perfect circles and no `rounded-full` anywhere. "Slightly more rounded" buttons in section 16 must stop at `--r-3` (8px). A pill button would violate the system, and the brief itself says not to make pills.
3. **State is communicated by shape, not hue.** `StatusChip` distinguishes states with `solid` / `outline` / `dashed` / `dotted` / `muted` borders. This already satisfies the accessibility rule "do not rely solely on colour" - and it means the activity micro-chart must not introduce colour coding either.
4. **`@theme inline` re-exports every custom property as a Tailwind utility.** So `--surface-2` is reachable as `bg-surface-2` in components. The consequence is decisive for light mode: **overriding the base `:root` custom properties inside `[data-theme="light"]` propagates to every utility in the app automatically.** You do not need to touch components. This is the clean insertion point and the only one you should use.
5. **A root `data-*` attribute precedent already exists.** `lib/preferences.ts` drives `[data-density="compact"]`, `[data-text-size="large"]` and `[data-reduce-motion="true"]`. Theme must follow that exact pattern - not `class="dark"`, not a context provider, not `next-themes`.
6. **The grain overlay occupies `body::after`** at `z-index: var(--z-grain)` = 9999. The grid therefore goes on **`body::before`**. Do not fight the grain; layer beneath it.

---

## 20.1 Branding (section 13)

### Every occurrence

All of these are on the branch. Grep confirms no others.

| File | Occurrence |
|---|---|
| `lib/copy.ts` | `brand = { name: "Nexus", tagline: "Voice support that respects your time.", version: "Version 1.0.0" }` |
| `lib/copy.ts` | `login.title = "Nexus"` |
| `lib/copy.ts` | `about.tagline` |
| `routes/__root.tsx` | `title: "Nexus Customer Portal"` |
| `routes/__root.tsx` | description "...for Nexus voice support..." |
| `routes/__root.tsx` | `{ name: "author", content: "Nexus" }` |
| `routes/__root.tsx` | `og:title` "Nexus Customer Portal" |
| `routes/__root.tsx` | `og:description` "Private voice support that respects your time." |
| `routes/__root.tsx` | `{ name: "twitter:site", content: "@Nexus" }` |
| `routes/_portal/assistant.tsx` | head `"Assistant - Nexus Customer Portal"`, body "the Nexus assistant" |
| `routes/_portal/billing.tsx` | head `"Billing - Nexus Customer Portal"`, body "What you owe Nexus" |
| `routes/_portal/activity.tsx` | head `"Activity - Nexus Customer Portal"` |
| `lib/preferences.ts` | `const KEY = "nexus_portal_preferences"` |
| `styles.css` | header comment `NEXUS CUSTOMER PORTAL - THE MONOCHROME EXPERIENCE BIBLE` |

### The name

I am not choosing your product name - that is a business decision and inventing one would be exactly the kind of unrequested decision the brief warns against. **Pick one and set it in a single place.** For the patch below the placeholder is `BRAND_NAME`.

Constraints for whatever you choose: it must work as a wordmark in a strictly monochrome, Geist-typeset interface; it must not need a colour to read as itself; and it must suit the future admin dashboard, so avoid anything with "portal" or "client" baked in.

### The structural fix, which matters more than the string

The real defect is not the word "Nexus" - it is that the brand name is **hardcoded in seven places**. Renaming in place would leave you with the same problem under a different name. Centralise first:

```ts
// lib/copy.ts
export const brand = {
  name: "BRAND_NAME",
  /** Suffix for document titles. Every route head must derive from this. */
  titleSuffix: "BRAND_NAME Customer Portal",
  tagline: "Voice support that respects your time.",
  version: "Version 1.0.0",
} as const;

/** Build a document title. Use this in every route head - never a literal. */
export const pageTitle = (section?: string) =>
  section ? `${section} - ${brand.titleSuffix}` : brand.titleSuffix;
```

Then each route head becomes `title: pageTitle("Assistant")`, and `__root.tsx` becomes `title: pageTitle()`. `og:title` and the author meta read `brand.name`. After this, a future rebrand is a one-line change - which is what "centralised app metadata/branding" in section 25 means.

Body-copy occurrences ("the Nexus assistant", "What you owe Nexus") should be reworded to not name the brand at all: "the assistant", "What you owe". Product surfaces inside a branded shell do not need to repeat the brand, and it removes two more interpolation sites.

### Favicon

`public/favicon.ico` is the stock file and `__root.tsx` links it as `image/x-icon`. Replace with a monochrome mark:

- `public/favicon.svg` - single-path monochrome mark, `currentColor`, works at 16px.
- `public/favicon-dark.svg` - inverted, for browsers honouring `prefers-color-scheme` in the tab strip.
- Keep a 32x32 `favicon.ico` for legacy.
- Add `public/apple-touch-icon.png` at 180x180 on a solid `--n-1` field.

Links in `__root.tsx`:

```tsx
{ rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },
{ rel: "icon", href: "/favicon.ico", sizes: "32x32" },
{ rel: "apple-touch-icon", href: "/apple-touch-icon.png" },
```

At 16px a wordmark is illegible. Use a single geometric glyph derived from the orb - the orb is already the product's visual signature and reusing it costs nothing.

### Storage key migration - do not skip this

`preferences.ts` persists to `nexus_portal_preferences`. Renaming it blindly silently resets every existing user's density, text-size, reduce-motion and captions settings. Migrate on read:

```ts
const KEY = "portal_preferences";
const LEGACY_KEY = "nexus_portal_preferences";

function read(): PortalPreferences {
  if (typeof window === "undefined") return DEFAULTS;
  const raw = window.localStorage.getItem(KEY) ?? window.localStorage.getItem(LEGACY_KEY);
  // ... existing parse logic unchanged
}
```

Write only to `KEY`; the legacy entry ages out naturally. Do not delete it in the same release - a user who rolls back would lose their settings.

---

## 20.2 Premium grid background (section 14)

CSS only. No image asset - the brief forbids a large background asset when CSS suffices, and two `repeating-linear-gradient` layers cost nothing.

```css
/* Add to the token block in :root */
--grid-line: rgba(255, 255, 255, 0.028);
--grid-line-major: rgba(255, 255, 255, 0.045);
--grid-cell: 64px;
--grid-major: 256px;
--grid-fade: 62%;
```

```css
/*
  Premium grid. Sits on body::before, beneath every app surface and beneath the
  grain on body::after. Two scales - a fine 64px cell and a 256px major line -
  give depth without adding density. A radial mask fades the grid out toward
  the edges so it reads as depth rather than as graph paper, and keeps the
  centre of the screen (where the orb and all primary text live) at its
  quietest.
*/
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image:
    repeating-linear-gradient(to right, var(--grid-line) 0 1px, transparent 1px var(--grid-cell)),
    repeating-linear-gradient(to bottom, var(--grid-line) 0 1px, transparent 1px var(--grid-cell)),
    repeating-linear-gradient(to right, var(--grid-line-major) 0 1px, transparent 1px var(--grid-major)),
    repeating-linear-gradient(to bottom, var(--grid-line-major) 0 1px, transparent 1px var(--grid-major));
  mask-image: radial-gradient(ellipse 120% 100% at 50% 40%, #000 0%, #000 var(--grid-fade), transparent 100%);
  -webkit-mask-image: radial-gradient(ellipse 120% 100% at 50% 40%, #000 0%, #000 var(--grid-fade), transparent 100%);
}

/* Tighter cell on small screens so the grid does not read as three huge boxes. */
@media (max-width: 640px) {
  :root { --grid-cell: 44px; --grid-major: 176px; }
}
```

Why each number:

- **0.028 opacity** matches the existing grain opacity exactly (`opacity: 0.028` on `body::after`). Using the same value means the two textures sit at one perceptual depth instead of competing. Against `--n-1: #0a0a0a` this renders around `#0d0d0d` - present, not readable as a line until you look for it.
- **64px cell** is `--sp-8` doubled, so the grid is commensurate with the spacing scale. Cards on the 8px grid land on grid lines rather than a few pixels off, which is the difference between deliberate and accidental.
- **The radial mask is the whole trick.** An unmasked grid is a cheap sci-fi template - that is the exact failure the brief names. Fading toward the edges and keeping the quietest area at 50% 40% (where the orb sits) means the grid never competes with the orb or with body text.
- **`position: fixed`** means the grid does not scroll with content, so it reads as a backdrop. It also means no repaint on scroll.
- **`z-index: 0`** with `pointer-events: none`: beneath every surface, above nothing interactive. Verify no app surface uses a negative z-index.

Do **not** add gradients, glows, particles, animation, or a vignette on top. The brief asks for premium restraint and one masked grid delivers it.

---

## 20.3 Light mode (section 15)

### Why `[data-theme="light"]` overriding base tokens is the correct approach

Because `@theme inline` re-exports the custom properties, redefining them under a root attribute selector re-themes every component with zero component edits. That satisfies "use the existing theme/token architecture" and "do not introduce raw arbitrary colors throughout individual components" simultaneously.

### The greys

Not an inversion. An inversion gives you `#ffffff` page backgrounds with `#000000` text, which is harsh and loses the layered-surface hierarchy the dark theme depends on. Compress the range instead, keeping the *relationships*:

```css
/*
  Light theme. Dark remains the default and lives in :root; this block only
  overrides. The scale is inverted in direction but compressed in range: the
  page sits at #fafafa rather than pure white and ink tops out at #0a0a0a
  rather than pure black, which preserves the dark theme's layered-surface
  feel and avoids the glare of a pure-white sheet. Still strictly achromatic -
  R === G === B on every value.
*/
[data-theme="light"] {
  --n-0: #ffffff;
  --n-1: #fafafa;
  --n-2: #f4f4f4;
  --n-3: #ededed;
  --n-4: #e4e4e4;
  --n-5: #d8d8d8;
  --n-6: #c4c4c4;
  --n-7: #a8a8a8;
  --n-8: #8a8a8a;
  --n-9: #6b6b6b;
  --n-10: #474747;
  --n-11: #262626;
  --n-12: #0a0a0a;
}
```

The surface and ink aliases (`--surface-0..5`, `--ink-1..5`) reference `--n-*`, so they follow automatically. Verify that in the branch before relying on it - if any alias holds a literal hex, redeclare it here too.

### The hardcoded values that will break - all of them

These hold literal rgba or a fixed `--n-*` and will not follow the palette. Every one must be redeclared:

| Location | Dark value | Light treatment |
|---|---|---|
| `--stroke-subtle/default/strong/ink` | `rgba(255,255,255,.06/.09/.14/.24)` | `rgba(0,0,0,.07/.10/.16/.26)` - slightly higher, dark-on-light needs more to read |
| `--elev-0..4` | inset `rgba(255,255,255,...)` | Real drop shadows: `0 1px 2px rgba(0,0,0,.05)` up to `0 12px 32px rgba(0,0,0,.12)`. Light-mode elevation is cast shadow, not inset highlight |
| `--glow-soft/strong/line` | white glows | Reduce heavily or set to `none`. A white glow on a light field is invisible; a dark "glow" is a shadow. Do not invert |
| `@utility focus-ring` | `outline: 2px solid var(--n-12)` | Tokenise: add `--focus-ring-color: var(--n-12)` in `:root`, override to `var(--n-12)` in light (which is now near-black), and change the utility to use the token. **Without this the focus ring becomes white-on-white and keyboard navigation is invisible - an accessibility regression, not a cosmetic one** |
| `@utility hatch-45` | `rgba(0,0,0,0.3)` | `rgba(0,0,0,0.08)` - it is already dark, so it goes from subtle-on-dark to too-strong-on-light |
| `::selection` | `background: var(--n-12); color: var(--n-0)` | Follows the palette automatically once `--n-*` flip. Verify contrast |
| Scrollbar thumb | `var(--n-6)` / hover `var(--n-7)` | Follows automatically. Verify visibility against `--surface-1` |
| `.skeleton` | `--surface-3` to `--surface-4` shimmer | Follows automatically. Check the shimmer is still perceptible - the light-mode steps are closer together, so widen to `--surface-2` to `--surface-4` if flat |
| `body::after` grain | `opacity: .028; mix-blend-mode: overlay` | `overlay` on a light field lightens rather than adds texture. Use `multiply` at `opacity: .02` |
| `body::before` grid | `rgba(255,255,255,...)` | `--grid-line: rgba(0,0,0,0.035)`, `--grid-line-major: rgba(0,0,0,0.055)`. Dark lines on light need marginally more opacity |

### Persistence

Extend `lib/preferences.ts`. It currently has no theme key.

```ts
export type PortalTheme = "dark" | "light";

export type PortalPreferences = {
  theme: PortalTheme;   // added
  reduceMotion: boolean;
  density: "comfortable" | "compact";
  textSize: "default" | "large";
  captions: boolean;
};

const DEFAULTS: PortalPreferences = {
  theme: "dark",         // dark is and remains the default
  // ... rest unchanged
};
```

Apply it exactly the way the existing three attributes are applied - the same effect, the same `document.documentElement.setAttribute` call site. Do not add a provider.

**Set the attribute before first paint** or every light-mode user gets a dark flash on load. Add a tiny inline script in `__root.tsx`'s document shell that reads `localStorage` and sets `data-theme` synchronously. This is the one place inline script is justified; it is the standard solution and there is no alternative that avoids the flash.

Expose the toggle in Preferences beside the existing density and text-size controls, using the same `Segmented` primitive. Two options, Dark first. Do not put a theme toggle in the topbar - it is a preference, and the portal already has a home for preferences.

---

## 20.4 Button refinement (section 16)

Current `Button` in `primitives.tsx`: `rounded-r-2` (6px), `transition-colors duration-200`, sizes `h-7` / `h-9` / `h-11`, five variants, **no press feedback and no hover motion**.

Minimal, system-respecting change:

```tsx
// base classes
"... rounded-r-3 transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] active:scale-[0.985] disabled:pointer-events-none disabled:opacity-40 ..."
```

Each change justified:

- **`rounded-r-2` to `rounded-r-3`** - 6px to 8px. "Slightly more rounded", stays well under the 12px ceiling, and matches `Card`'s radius so buttons and cards agree.
- **`active:scale-[0.985]`** - the press feedback that is currently missing. 1.5% is felt, not seen. This is the single highest-value change in the section: the buttons feel conventional mainly because nothing happens when you press them.
- **`transition-colors` widened to include `transform` and `box-shadow`**, on the existing `--ease-out` curve rather than the default linear-ish easing. Same duration.
- **`disabled:opacity-40` plus `disabled:pointer-events-none`** - a consistent disabled treatment across all five variants instead of per-variant handling.

For the primary variant only, add a restrained hover lift:

```tsx
// primary variant
"... hover:shadow-[var(--elev-2)] ..."
```

No `translateY`. Lifting a button on hover is the flashy move the brief rules out; a shadow step is enough.

`Start conversation` gets `size="lg"` (`h-11`) and nothing else special. It is already the only primary-variant button on the tab, so hierarchy is established by variant, not by making it bigger. Resist adding a gradient, a border glow, or an icon animation.

Respect reduced motion - `styles.css` already forces `transition-duration: 0.001ms` under `[data-reduce-motion="true"]` and `prefers-reduced-motion`, which covers `active:scale` automatically since it is a CSS transition. Verify, do not assume.

Verify the focus ring in **both** themes after the `--focus-ring-color` tokenisation. Every variant, keyboard-only.

---

## 20.5 Activity micro-metric (section 9)

### What real data exists

From `me_reads.conversations()`, each list item has exactly: `session_id`, `channel`, `started_at`, `ended_at`, `duration_seconds`, `disposition`, `turns` (an integer). That is all. No per-turn timing in the list payload, no sentiment, no token counts.

So: **a sparkline of conversational activity over time is not possible from the list endpoint**, and fetching per-conversation detail for every card to draw one would be a gratuitous N+1. Do not do it, and do not synthesise the shape - the brief is explicit that inventing analytical data to justify a chart is forbidden.

### What is honest

The two real numbers are `turns` and `duration_seconds`. Their ratio - average seconds per turn - is genuinely meaningful: it distinguishes a brisk exchange from a slow one, and it is derived, not invented.

Render a **turn-density bar**: a thin horizontal bar showing this conversation's turn count relative to the largest turn count in the currently loaded page.

```tsx
/*
  Turn-density bar. Renders one real metric - this conversation's turn count as
  a proportion of the busiest conversation in the loaded page. No synthetic
  data, no per-turn timing (the list endpoint does not return any). Pure CSS,
  no charting dependency: at this size a div is the correct implementation.
*/
function TurnDensity({ turns, max }: { turns: number; max: number }) {
  const ratio = max > 0 ? Math.min(turns / max, 1) : 0;
  return (
    <div
      className="h-1 w-full overflow-hidden rounded-r-0 bg-surface-3"
      role="img"
      aria-label={`${turns} turns`}
    >
      <div
        className="h-full bg-ink-4 transition-[width] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]"
        style={{ width: `${ratio * 100}%` }}
      />
    </div>
  );
}
```

Why this and not a sparkline or donut:

- **1px tall.** It adds no meaningful vertical height - the brief's hard constraint. Card proportions are untouched.
- **No dependency.** Two divs. Adding recharts or visx for this would be exactly the "heavy charting library for a tiny visual metric" the brief forbids.
- **Achromatic**, using `bg-ink-4` on `bg-surface-3`, so it works in both themes with no extra light-mode rule.
- **`role="img"` with an `aria-label`** carrying the actual number, so the bar is not information-only-in-colour and screen readers get the value. The numeric turn count stays visible in the `MetricTile` regardless, so the bar is purely reinforcing.

Compute `max` once per page in the list component, not per card:

```tsx
const maxTurns = useMemo(
  () => items.reduce((m, c) => Math.max(m, turnCount(c.turns)), 0),
  [items],
);
```

Use `turnCount()` from cookbook 17 - it accepts both the list's integer and the detail's array, so the bar can never be handed the shape that produced `[object Object]`.

Place it directly beneath the existing metric row, inside the existing card padding. `MetricTile`'s props (`label`, `value`, `hint`, `size`, `pending`) are **not** changed - the bar is a sibling, so nothing that already uses `MetricTile` is affected.

Honest caveat to state plainly: relative-to-page-max means the bar rescales as you paginate. That is acceptable for a comparative glance within a page and it is truthful; an absolute scale would need a global max the list endpoint does not provide. Do not add a backend field for this - it is not worth an endpoint change.

---

## 20.6 Verification

```bash
npm run typecheck
npm test
npx eslint src/
npm run build
```

Add these to `scripts/verify-portal.sh` (currently 13 checks):

```bash
# 14 - no residual generic branding
! grep -rniq "nexus" src/ || { echo "FAIL: Nexus reference remains"; exit 1; }

# 15 - route heads derive from the centralised title helper
! grep -rq "Customer Portal\"" src/routes/_portal/ || { echo "FAIL: hardcoded title"; exit 1; }

# 16 - light theme block present
grep -q '\[data-theme="light"\]' src/styles.css || { echo "FAIL: no light theme"; exit 1; }

# 17 - focus ring is tokenised, not a literal grey
grep -q -- "--focus-ring-color" src/styles.css || { echo "FAIL: focus ring not tokenised"; exit 1; }

# 18 - grid background present on body::before
grep -q "body::before" src/styles.css || { echo "FAIL: no grid background"; exit 1; }
```

Check 14 is the one that matters most - it makes the branding removal permanent instead of a one-time sweep.

### Browser acceptance

**Branding**
1. Tab title on every route reads `<Section> - <BRAND> Customer Portal`.
2. Favicon renders at 16px and is legible; check both a light and a dark browser chrome.
3. Login screen wordmark; no "Nexus" anywhere in the DOM (`document.body.innerHTML.includes("Nexus") === false`).
4. Existing user with `nexus_portal_preferences` in localStorage: settings survive the key migration. Test this explicitly - set a non-default density under the old key, then load.

**Grid**
5. Visible as depth, not as graph paper. Step back from the screen: it should register as texture.
6. Body text at `--ink-4` and `--ink-5` still fully readable over it.
7. Does not compete with the orb on the assistant tab, mid-call and at rest.
8. Not visible through cards - card surfaces must be opaque.
9. Does not scroll with content; no jank while scrolling a long billing list.
10. At 390px wide the tighter cell applies and the grid does not read as three boxes.

**Light mode**
11. Sweep every route: assistant (both states), activity (list and detail), billing (prepaid and postpaid), services, profile, preferences, security, requests, help, login, 404, error boundary.
12. Every text element readable. Check `--ink-5` muted text specifically - it is the first casualty of a compressed light scale.
13. Card borders visible against the page. Nested surfaces still distinguishable.
14. Focus rings visible on every interactive element. Keyboard-only pass. **This is the regression most likely to slip through.**
15. Skeletons perceptible while loading.
16. All `StatusChip` tones distinguishable - remember they differ by border style, so confirm dashed vs dotted still reads.
17. Scrollbar thumb visible.
18. Text selection legible.
19. Grain does not wash the page out (`multiply`, not `overlay`).
20. Toggle theme mid-call on the assistant tab: no LiveKit disruption, no orb flicker, no dropped transcript.
21. Reload with light active: **no dark flash**. This validates the pre-paint script.
22. Dark mode after all of this is pixel-identical to `version_96`. Compare screenshots. Non-negotiable - the brief requires no dark-mode regression.

**Buttons**
23. All five variants, all three sizes, both themes: rest, hover, active, disabled, focus-visible.
24. Press feedback felt on `Start conversation` and on `End`.
25. Reduced motion on: no scale animation, states still distinguishable.

**Activity metric**
26. Card height essentially unchanged from `version_96`. Measure it.
27. Bar proportions correct against the visible turn counts.
28. A conversation with 0 turns renders an empty track, not a broken bar or `NaN`.
29. A single-item page renders a full bar (max === self) - confirm that reads acceptably rather than looking like an error.
30. Screen reader announces the turn count from the `aria-label`.
31. Both themes, 1440 / 1024 / 390.

### Definition of done for cookbook 20

- No "Nexus" string anywhere in `src/`; verify-portal check 14 enforces it.
- All titles and metadata derive from `copy.brand` via `pageTitle()`.
- New favicon set, legible at 16px.
- Preferences key migrated without data loss.
- Grid present, subtle, masked, fixed, CSS-only, no new asset.
- Light mode complete across every route, achromatic, token-driven, no component-level colours.
- Focus ring tokenised and visible in both themes.
- Dark mode unchanged and still the default; no flash on load.
- Buttons refined within the 12px radius ceiling, with press feedback and a consistent disabled state.
- Activity cards carry one honest derived metric, no dependency added, height unchanged.
- No fabricated data anywhere.
