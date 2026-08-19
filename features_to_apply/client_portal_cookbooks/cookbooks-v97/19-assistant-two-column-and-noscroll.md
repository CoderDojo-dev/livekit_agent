# Cookbook 19 - Assistant two-column call layout and no-scroll composition

Base: `version_96` @ `fa220abc85ed498bc83e158d6596d4510b87441f`.
Scope: layout and motion in `routes/_portal/assistant.tsx`, plus one placement change in `components/assistant/live-stream.tsx`. **No logic change.** No change to the orb, to `voice-session.tsx`, to `use-orb-level.ts`, to the LiveKit wiring, or to any state machine.

The brief is explicit: do not redesign the tab. Every component, string, type token and status chip stays exactly as it is. What changes is where the boxes sit and how they move.

---

## 19.1 What is actually wrong

On the branch, the whole tab is one centred column:

```tsx
<div className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center gap-sp-9">
```

Three consequences, all of them the reported symptoms:

1. **`justify-center` plus `min-h`, not `h`.** The column centres its content while being free to grow past the viewport. Every child added during a call - state copy, error, controls, two status chips, `LiveStream`, then the post-call summary card - pushes the total height beyond `100vh - 8rem`. The container then scrolls as a page, and because content is *centred*, growth pushes items off **both** ends. That is precisely why "Your conversation will appear here as you speak." ends up below the fold: it is not positioned too low by mistake, it is being pushed out by the elements below it.
2. **No two-column composition exists.** `flex-col` is unconditional. There is no `inCall` branch in the layout, so the orb has nowhere to move to and the transcript has no right-hand column to occupy.
3. **The scroll region is the page.** `portal-shell.tsx` renders `<main className="... mx-auto w-full max-w-6xl px-sp-8 py-sp-9">` and the shell already declares "une seule zone de defilement" - one scroll region. The assistant is currently violating that by growing the shared page scroller instead of absorbing its own overflow.

Two things are already right and must be preserved:

- `LiveStream` caps at `MAX_VISIBLE_ITEMS = 3` and fades older items out with `AnimatePresence mode="popLayout"`. **The transcript cannot grow unboundedly.** So section 8 of the brief needs no new virtualisation, no scroll-to-bottom controller, and no "over-engineered chat interface" - the growth problem is the page container, not the transcript.
- `ORB_SIZE.call` / `ORB_SIZE.rest` with `transition-[width,height] duration-500` already resizes the orb between states. Reuse it; do not replace it.

---

## 19.2 The `scene` prop already exists

`portal-shell.tsx` takes a prop that is currently unused by any route:

```tsx
export function PortalShell({ children, scene = false }: { children: ReactNode; scene?: boolean }) {
  ...
  scene ? "flex" : "mx-auto w-full max-w-6xl px-sp-8 py-sp-9",
```

That is the intended hook for a full-bleed, height-owning route. It was built for exactly this and never wired up. Use it rather than inventing a new mechanism - this is the "already implemented, partially wired" case the brief asks you to look for.

`_portal.tsx` renders `<PortalShell>` with no props, so wiring `scene` requires making it path-aware. Keep it declarative and minimal:

```tsx
// routes/_portal.tsx
const pathname = useRouterState({ select: (s) => s.location.pathname });
...
<PortalShell scene={pathname === "/assistant"}>
```

`pathname` is already selected in that component for `TabPanel`, so no new subscription is added.

In `PortalShell`, the scene branch needs to own its height rather than only `flex`:

```tsx
scene
  ? "flex min-h-0 flex-col overflow-hidden px-sp-8 py-sp-7"
  : "mx-auto w-full max-w-6xl px-sp-8 py-sp-9",
```

and the wrapper above it must stop being `min-h-screen` in scene mode, or the child can never be height-bounded:

```tsx
// the inner column wrapper
cn(
  "flex flex-col transition-[padding] duration-300",
  scene ? "h-screen overflow-hidden" : "min-h-screen",
  collapsed ? "lg:pl-16" : "lg:pl-64",
)
```

`h-screen` + `overflow-hidden` + `min-h-0` on the flex child is the whole no-scroll mechanism. `min-h-0` is the non-obvious part: a flex child defaults to `min-height: auto`, which refuses to shrink below its content and is the single most common cause of "I set overflow-hidden and it still scrolls".

Also drop `pb-20` in scene mode - it exists to clear the mobile `PortalTabbar` and would otherwise eat 80px of the scene's height. Apply the tabbar clearance as `pb-20 lg:pb-0` inside the scene's own scrolling child instead.

---

## 19.3 The two-column composition

Replace the single centred column in `assistant.tsx`. `oldStr`:

```tsx
<div className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center gap-sp-9">
```

The structure to build in its place - a two-cell grid whose second cell has zero width until a call starts:

```tsx
{/*
  One grid, two states. The stage column always exists; the transcript column
  is a real grid track that animates from 0fr to 1fr, so the orb slides left as
  a consequence of the track resizing rather than being translated by hand.
  That keeps the orb in normal flow - no absolute positioning, no transform
  origin to fight, and the restore on disconnect is the same animation run
  backwards.
*/}
<div className="flex h-full min-h-0 w-full flex-col">
  <motion.div
    layout
    className="grid min-h-0 flex-1 items-center gap-sp-8 lg:gap-sp-10"
    animate={{
      gridTemplateColumns: inCall ? "minmax(0,0.85fr) minmax(0,1.15fr)" : "minmax(0,1fr) minmax(0,0fr)",
    }}
    transition={reduce ? { duration: 0 } : T_STAGE}
  >
    {/* Column 1 - the stage: orb, state copy, controls. Always mounted. */}
    <motion.div layout className="flex min-h-0 flex-col items-center justify-center gap-sp-7">
      {/* existing Orb + OrbPlinth, unchanged */}
      {/* existing state copy block, unchanged */}
      {/* existing error block, unchanged */}
      {/* existing CallBar / controls, unchanged */}
      {/* existing StartAudioButton, unchanged */}
      {/* existing StatusChips, unchanged */}
    </motion.div>

    {/* Column 2 - the transcript. Overflow lives here and nowhere else. */}
    <div className="flex h-full min-h-0 items-center justify-center overflow-hidden">
      <AnimatePresence initial={false}>
        {inCall ? (
          <motion.div
            key="transcript"
            className="flex h-full max-h-full min-h-0 w-full flex-col overflow-y-auto"
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 12 }}
            transition={reduce ? { duration: 0 } : T_PANEL}
          >
            <LiveStream key={callId} /* existing props unchanged */ />
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  </motion.div>

  {/* Post-call summary stays below the stage, outside the grid. */}
</div>
```

Key decisions and why:

- **Animate the grid track, not the orb.** Translating the orb with `x` would need a measured offset, would break at every breakpoint, and would leave a hole in the layout. Animating `gridTemplateColumns` from `0fr` to `1.15fr` makes the orb slide left because its own track shrank. It is one animated property, it is breakpoint-independent, and the reverse is free.
- **`layout` on the stage column** lets Framer Motion interpolate the orb's real position change rather than snapping it. Combined with the existing `transition-[width,height] duration-500` on the orb itself, the orb shrinks and slides as one gesture. That is the "premium, not a CSS jump" requirement.
- **`AnimatePresence` on the transcript**, keyed on `inCall`, gives the fade-and-slide in and a matching exit on disconnect. Because `inCall` is already `session.connectionState !== "disconnected"`, **every** disconnect path is covered at once - user hangs up, agent leaves, LiveKit drops. No new event handling.
- **`overflow-y-auto` on the transcript only.** This is the single internal scroller the brief asks for. With `MAX_VISIBLE_ITEMS = 3` it will rarely engage; it is there so a long agent paragraph cannot push the page.
- **`items-center` on the grid** keeps the orb vertically centred in the stage column during a call, so it stays visually stable while the transcript changes - section 8's requirement.

Add one motion token next to the existing ones. Do not invent a duration inline:

```tsx
// components/portal/data.tsx, beside T_MICRO / T_BASE / T_PANEL
/** Stage transition: the orb moving between centred and left. Slower than a
 *  panel because it carries the largest element on screen. */
export const T_STAGE = { duration: 0.48, ease: EASE_OUT } as const;
```

0.48s is deliberate: it is `--d-6` (420ms) rounded to the same family as the orb's existing 500ms width/height transition, so the two read as one movement instead of two.

Import `T_STAGE` and `T_PANEL` from `@/components/portal/data` - `T_BASE` is already imported there, so this adds names to an existing import, not a new one.

### Reduced motion

Take the hook that is already used elsewhere in the codebase:

```tsx
import { useReducedMotion } from "motion/react";
const reduce = useReducedMotion();
```

With `reduce` true, pass `{ duration: 0 }`. The layout still changes - the orb still ends up left, the transcript still appears - it just arrives instantly. The brief requires interactive elements to remain understandable without animation, and `data.tsx` already sets this precedent in `TopProgress`. Note that `styles.css` also forces `transition-duration: 0.001ms` under both `prefers-reduced-motion` and `[data-reduce-motion="true"]`, which covers the orb's Tailwind transition but **not** Framer Motion's JS-driven animations - hence the explicit prop.

---

## 19.4 The intro text

`"Your conversation will appear here as you speak."` is `copy.assistant.stream.willAppear`, returned by `LiveStream` itself in its pre-connect branch:

```tsx
if (!session.isConnected && items.length === 0) {
  return (
    <p className="t-caption text-ink-5" aria-hidden="true">
      {copy.assistant.stream.willAppear}
    </p>
  );
}
```

In the new structure the transcript column has zero width before a call, so this branch would render into a collapsed track and be invisible. That is worse than today.

Fix it by placing the pre-call hint in the **stage** column, where the rest of the pre-call copy already lives, and letting `LiveStream` render only during a call. In `assistant.tsx`, inside the stage column below the state copy:

```tsx
<AnimatePresence initial={false}>
  {!inCall ? (
    <motion.p
      key="will-appear"
      className="t-caption text-center text-ink-5"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={reduce ? { duration: 0 } : T_MICRO}
    >
      {copy.assistant.stream.willAppear}
    </motion.p>
  ) : null}
</AnimatePresence>
```

The string moves; it is not duplicated and not reworded. `LiveStream`'s own pre-connect branch becomes dead code in the portal because the component is only mounted when `inCall` - leave the branch in place, since `LiveStream` is a port of the client-widget component and removing the branch would diverge the two files for no benefit.

Drop `aria-hidden="true"` when you move it. It was hidden because it sat next to an `aria-live` region; in the stage column it is ordinary descriptive text and should be readable by a screen reader.

---

## 19.5 Vertical budget

The brief asks for calculated spacing, not smaller numbers everywhere. The scene has a fixed budget, so state it:

| Consumer | Height |
|---|---|
| Topbar | `h-16` = 64px |
| Scene padding | `py-sp-7` = 20px top + bottom = 40px |
| Mobile tabbar | 80px, `lg:` 0 |

So the stage gets `100vh - 104px` on desktop. Everything inside must fit that without a page scroll, at 700px tall as well as 1080.

Changes to the existing stack, all of them reductions in *reserved* space rather than in component size:

- Outer gap `gap-sp-9` (32px) becomes `gap-sp-7` (20px) inside the stage column, and the grid's own `gap-sp-8` / `lg:gap-sp-10` separates the two columns horizontally. The vertical rhythm tightens by one step on the existing scale; no new value is introduced.
- The state-copy block's `min-h-[72px]` and the controls' `min-h-14` are **reservations to prevent layout shift between states**. Keep them. They are the correct pattern and removing them would make the orb jitter every time the agent state changes. This is the "do not solve layout with arbitrary heights" rule cutting the other way: these two are justified, an arbitrary height on the transcript would not be.
- The orb already has `ORB_SIZE.call` smaller than `ORB_SIZE.rest`, so the tallest element shrinks exactly when the transcript needs room. Verify the two values still leave headroom at 700px; if not, reduce `ORB_SIZE.call` only, and only via the existing constant.
- Below `lg`, collapse to one column and let the transcript take the lower half: `grid-cols-1` with the stage on top. Do **not** try to keep two columns on a phone. Set the grid animation to only apply from `lg` up by animating a CSS custom property, or simpler and preferable: gate the two-column animation behind a `lg` media query check and render the mobile case as a plain stacked flex column with the transcript scrolling. Simpler is right here - a phone in a voice call does not need a side-by-side view.

---

## 19.6 Verification

```bash
npm run typecheck
npm test
npx eslint src/routes/_portal/assistant.tsx src/routes/_portal.tsx src/components/shell/portal-shell.tsx src/components/portal/data.tsx src/components/assistant/live-stream.tsx
npm run build
```

### Layout acceptance - do this at three viewport heights

Test at **1080, 800 and 700** px tall, and at 1440 / 1024 / 390 wide. Height is the sensitive axis and the brief says so explicitly.

1. Land on Assistant. Orb centred. Intro text `"Your conversation will appear here as you speak."` visible **without scrolling**. Start conversation button visible. Both status chips visible.
2. Confirm the page has no vertical scrollbar. `document.scrollingElement.scrollHeight === clientHeight`. This is the objective check for section 7 - do it in the console, not by eye.
3. Click Start conversation. The orb and its controls glide left as one movement; the transcript column expands from the right; nothing jumps or reflows twice.
4. Speak. New transcript items appear on the right and remain visible with **no page scroll**. Older items fade as the 3-item cap engages.
5. Let the agent produce a long answer. The transcript column scrolls internally; the orb does not move; the page still does not scroll.
6. End the call from the UI. The transcript fades out, the column collapses, the orb glides back to centre. Not abrupt.
7. Repeat the disconnect three more ways: kill the agent worker; stop LiveKit; disconnect the network. All three must restore the centred layout, because all three drive `session.connectionState`.
8. Start and end twice in a row. No drift in the orb's resting position, no leftover width in the transcript track.
9. At 390 wide: single column, transcript below the orb, no horizontal scroll, tabbar not overlapping content.
10. Enable OS reduce-motion. Layout still reaches both end states, instantly. Nothing is stuck mid-transition and nothing is invisible.
11. Keyboard only: tab to Start conversation, activate with Enter and Space, tab through mute and end. Focus rings visible against the stage in both states. Focus is never lost when the transcript column mounts or unmounts.
12. Navigate Assistant to Activity and back. The scene mode must not leak - Activity must keep its normal `max-w-6xl` centred page and its own page scrolling.
13. Confirm the post-call summary card still renders after a call and is reachable.

### Definition of done for cookbook 19

- No page scroll on the assistant tab at 700px tall or above.
- Intro text visible on landing without scrolling.
- Orb centred at rest, left during a call, animated both ways.
- Transcript on the right during a call, absorbing its own overflow.
- Orb visually stable while the transcript updates.
- Every disconnect path restores the centred layout smoothly.
- Single column below `lg`, no horizontal scroll.
- Reduced motion reaches both end states without animation.
- No component was redesigned, no string reworded, no logic changed, and the other tabs keep their existing page layout.
