import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  CalendarClock,
  Inbox,
  Layers2,
  MessageCircleQuestion,
  ReceiptText,
  TriangleAlert,
  UserRound,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { copy } from "@/lib/copy";
import { usePortalReducedMotion } from "@/hooks/use-portal-motion";
import { EASE_OUT, T_PANEL } from "@/components/portal/data";

/**
 * components/assistant/scene-backdrop.tsx — chapitre 40, le fond de la scene.
 *
 * The assistant screen is the only room in the portal with nothing in the
 * middle of it: one orb, one sentence, one button, and a great deal of empty
 * page around them. This component fills that page without putting anything
 * IN it.
 *
 * Five layers, in paint order, every one of them decorative and inert
 * (`pointer-events-none`, `aria-hidden`), sitting at z-0 under a stage that is
 * lifted to z-10 by the route:
 *
 *   1. BRACKETS — four corner rules. They frame the field, so the grid inside
 *      reads as a drawing with edges rather than a texture that ran out.
 *   2. GRID — 64px hairlines drifting exactly one cell per 24s. Radially
 *      masked, because an unmasked grid runs into the topbar and the rail and
 *      immediately reads as a rendering bug rather than as depth.
 *   3. AURORA — one achromatic light, breathing on a 20s cycle behind where
 *      the orb sits. It is the only thing here with any weight to it, and it
 *      is what keeps the near-black canvas from looking switched off.
 *   4. SCAN — a single hairline crossing the field every 11s. One pass, not a
 *      loop of many: it should be noticed about once per visit.
 *   5. PROMPTS — the only layer that means anything. Four slots, each holding
 *      one thing the assistant can actually do, rotating round-robin so the
 *      screen answers "what am I allowed to say?" before the customer has to
 *      ask. Never all at once: one slot changes at a time, which is a rhythm
 *      rather than a slideshow.
 *
 * THE CALL IS THE SUBJECT. Once a conversation starts the whole backdrop drops
 * to a quarter and the prompts leave entirely — during a call the transcript is
 * what the customer is reading, and wallpaper that keeps performing behind it
 * is wallpaper competing with the product.
 *
 * REDUCED MOTION: the CSS layers are already neutralised by the two blocks in
 * styles.css, which match on `*`. The prompt rotation is a JS timer that no
 * media query can reach, so it is never started at all — the four slots render
 * their opening prompt and hold. Nothing here is required to understand or
 * operate the screen.
 */

const PROMPT_ICONS: Record<string, LucideIcon> = {
  ask: MessageCircleQuestion,
  problem: TriangleAlert,
  bill: ReceiptText,
  balance: Wallet,
  request: Inbox,
  callback: CalendarClock,
  person: UserRound,
  plan: Layers2,
};

const PROMPTS = copy.assistant.prompts;

/**
 * WHERE A PROMPT LANDS.
 *
 * The four chips used to sit at four hard-coded corners, which after the second
 * rotation reads as four little signs bolted to the page rather than as things
 * drifting through it. Every appearance now picks a fresh spot.
 *
 * Random, but never *anywhere*. Three constraints shape the region:
 *
 *  1. THE ORB IS SACRED. The stage owns the middle of the screen — a 320px orb
 *     at rest, its two lines of state copy, and the start control under them.
 *     Chips are therefore confined to the two outer bands, addressed with the
 *     LOGICAL start/end insets so the scene mirrors correctly in Arabic.
 *  2. TWO CHIPS MUST NEVER COLLIDE. Rather than rejection-sampling and hoping,
 *     each of the four slots owns one band-half (start-upper, end-upper,
 *     start-lower, end-lower) and randomises only WITHIN it. Overlap is then
 *     impossible by construction rather than by luck, and the placement still
 *     lands somewhere new every single time.
 *  3. THE TWO SIDES MUST NOT LINE UP. The end-side bands are pushed a few
 *     percent down from the start-side ones, so a left and a right chip never
 *     form an accidental horizontal pair.
 *
 * BELOW md NO PROMPT RENDERS AT ALL. The orb is 320px at rest and a phone
 * column is 375px wide: there is no outer band left to place anything in. The
 * grid, the aurora and the scan still run — those cost nothing in width.
 */
type Placement = {
  /** Logical side, so the scene mirrors under dir="rtl". */
  side: "start" | "end";
  /** Distance from that edge, in percent. */
  inset: number;
  /** Distance from the top, in percent. */
  top: number;
  /** Phase offset for the CSS float, so two chips never breathe in unison. */
  floatDelay: number;
};

/** The four bands. Each is one slot's private region; they do not intersect. */
const BANDS = [
  { side: "start", insetFrom: 3, insetTo: 13, topFrom: 8, topTo: 30 },
  { side: "end", insetFrom: 3, insetTo: 12, topFrom: 15, topTo: 37 },
  { side: "start", insetFrom: 4, insetTo: 14, topFrom: 58, topTo: 80 },
  { side: "end", insetFrom: 3, insetTo: 13, topFrom: 64, topTo: 86 },
] as const;

function between(from: number, to: number): number {
  return from + Math.random() * (to - from);
}

function place(slot: number): Placement {
  const band = BANDS[slot % BANDS.length]!;
  return {
    side: band.side,
    inset: Number(between(band.insetFrom, band.insetTo).toFixed(2)),
    top: Number(between(band.topFrom, band.topTo).toFixed(2)),
    // A whole float cycle is 7s; spreading the offset across it means two chips
    // that happen to appear together still rise and fall out of step.
    floatDelay: Math.round(between(0, 7000)),
  };
}

/** Render order. Indices rather than the band objects: a band only decides
 *  where a chip MAY go, and the slot state decides where it currently is. */
const SLOT_INDICES = BANDS.map((_, index) => index);

/** One slot changes every this many ms. Four slots, so any given chip holds
 *  for roughly ten seconds — long enough to read twice without trying. */
const ROTATE_MS = 2600;

/** What one slot is showing: which prompt, and where. The two travel together
 *  in ONE state object on purpose — the position has to change on exactly the
 *  frame the prompt does, or the outgoing chip slides to the incoming chip's
 *  spot while it is still fading out. */
type Slot = { prompt: number; at: Placement };

export function SceneBackdrop({ inCall }: { inCall: boolean }) {
  const reduce = usePortalReducedMotion();

  /*
   * Opens with the first four prompts — the four most-asked things, in the
   * order copy.ts lists them — each already placed at random inside its band.
   *
   * Randomising in the initialiser is safe HERE and nowhere else in the portal:
   * this route is `ssr: false`, so there is no server render for the client to
   * disagree with. On any SSR route this would be a hydration mismatch.
   */
  const [slots, setSlots] = useState<Slot[]>(() =>
    BANDS.map((_, index) => ({ prompt: index, at: place(index) })),
  );

  useEffect(() => {
    // A rotation nobody asked to see is exactly the animation reduced motion
    // exists to switch off. The opening four stay where they are.
    if (reduce) return;

    let cursor = BANDS.length;
    let slot = 0;
    const timer = window.setInterval(() => {
      const at = slot;
      const next = cursor % PROMPTS.length;
      // New prompt AND new position in one update: they are one visual event.
      setSlots((previous) => {
        const draft = [...previous];
        draft[at] = { prompt: next, at: place(at) };
        return draft;
      });
      cursor += 1;
      slot = (slot + 1) % BANDS.length;
    }, ROTATE_MS);

    return () => window.clearInterval(timer);
  }, [reduce]);

  return (
    <motion.div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden"
      initial={false}
      // Not zero during a call: the field should still be there behind the
      // transcript, just demoted from scenery to texture.
      animate={{ opacity: inCall ? 0.28 : 1 }}
      transition={reduce ? { duration: 0 } : T_PANEL}
    >
      {/* 1 — the frame. */}
      <span className="scene-bracket absolute left-sp-5 top-sp-5 h-6 w-6 border-l border-t" />
      <span className="scene-bracket absolute right-sp-5 top-sp-5 h-6 w-6 border-r border-t" />
      <span className="scene-bracket absolute bottom-sp-5 left-sp-5 h-6 w-6 border-b border-l" />
      <span className="scene-bracket absolute bottom-sp-5 right-sp-5 h-6 w-6 border-b border-r" />

      {/* 2 — the field. */}
      <span className="scene-grid absolute inset-0" />

      {/* 3 — the light. Sized in vmin so it stays proportional to the room
             rather than to the column it happens to be sitting in. */}
      <span className="scene-aurora absolute left-1/2 top-[44%] h-[62vmin] w-[62vmin] -translate-x-1/2 -translate-y-1/2" />

      {/* 4 — the pass. */}
      <span className="scene-scan absolute inset-x-[12%] h-px bg-[var(--grid-line-lit)]" />

      {/* 5 — the prompts.
             The POSITIONED element is the one AnimatePresence keys on, so the
             outgoing chip finishes fading out where it was and the incoming one
             fades in at its new spot. Keying an inner span inside a positioned
             wrapper would instead drag the departing chip across the screen to
             the new coordinates first, which is the one motion this scene must
             never make. `mode="wait"` holds the slot empty in between, so a
             chip is never visible in two places at once. */}
      {SLOT_INDICES.map((index) => {
        const slot = slots[index];
        if (!slot) return null;
        const prompt = PROMPTS[slot.prompt] ?? PROMPTS[0]!;
        const Icon = PROMPT_ICONS[prompt.id] ?? MessageCircleQuestion;
        return (
          <AnimatePresence key={index} mode="wait" initial={false}>
            {!inCall ? (
              <motion.div
                // The placement is part of the key: a rotation that happens to
                // repeat a prompt still counts as a new appearance.
                key={prompt.id + "@" + slot.at.top}
                className="scene-float absolute hidden md:block"
                style={{
                  [slot.at.side === "start" ? "insetInlineStart" : "insetInlineEnd"]:
                    slot.at.inset + "%",
                  top: slot.at.top + "%",
                  ["--float-delay" as string]: slot.at.floatDelay + "ms",
                }}
                // The entrance every chip shares, unchanged from the fixed-slot
                // version: rise six pixels out of a four-pixel blur over 420ms,
                // and leave the same way.
                initial={reduce ? { opacity: 0 } : { opacity: 0, y: 6, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, filter: "blur(4px)" }}
                transition={reduce ? { duration: 0 } : { duration: 0.42, ease: EASE_OUT }}
              >
                <span className="t-ui inline-flex items-center gap-sp-4 rounded-r-3 border border-stroke-subtle bg-surface-1/50 px-sp-5 py-sp-3 text-ink-4 backdrop-blur-[2px]">
                  <Icon size={13} strokeWidth={1.5} className="shrink-0 text-ink-5" />
                  {prompt.label}
                </span>
              </motion.div>
            ) : null}
          </AnimatePresence>
        );
      })}
    </motion.div>
  );
}
