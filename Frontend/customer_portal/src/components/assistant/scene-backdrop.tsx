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
import { T_PANEL } from "@/components/portal/data";
import { cn } from "@/lib/utils";

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
 * Where the four prompts live.
 *
 * All four are pinned well outside the middle third, which belongs to the orb
 * and its copy, and all four sit in the OUTER half of their quadrant so that
 * when the stage narrows during a call they are already out of the way.
 * Measured at 1280x720: the four chips clear the 446px central stage region
 * entirely, with the nearest edge 250px away from it.
 *
 * BELOW md THE PROMPTS DO NOT RENDER AT ALL. The orb is 320px at rest and a
 * phone column is 375px wide, so there is no outer margin left to put a chip
 * in — anything placed there lands on top of the orb or on the state copy
 * underneath it. The grid, the aurora and the scan still run: those are the
 * layers that cost nothing in width.
 */
const SLOTS = [
  { key: "tl", position: "left-[6%] top-[14%]", float: 0 },
  { key: "tr", position: "right-[7%] top-[22%]", float: 1600 },
  { key: "bl", position: "left-[11%] bottom-[20%]", float: 3200 },
  { key: "br", position: "right-[6%] bottom-[15%]", float: 800 },
] as const;

/** One slot changes every this many ms. Four slots, so any given chip holds
 *  for roughly ten seconds — long enough to read twice without trying. */
const ROTATE_MS = 2600;

export function SceneBackdrop({ inCall }: { inCall: boolean }) {
  const reduce = usePortalReducedMotion();

  // Slot -> index into PROMPTS. Opens with the first four, which are the four
  // most-asked things, in the order copy.ts lists them.
  const [visible, setVisible] = useState<number[]>(() => SLOTS.map((_, index) => index));

  useEffect(() => {
    // A rotation nobody asked to see is exactly the animation reduced motion
    // exists to switch off. The opening four stay on screen.
    if (reduce) return;

    let cursor = SLOTS.length;
    let slot = 0;
    const timer = window.setInterval(() => {
      const at = slot;
      const next = cursor % PROMPTS.length;
      setVisible((previous) => {
        const draft = [...previous];
        draft[at] = next;
        return draft;
      });
      cursor += 1;
      slot = (slot + 1) % SLOTS.length;
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

      {/* 5 — the prompts. */}
      <AnimatePresence>
        {!inCall
          ? SLOTS.map((slot, index) => {
              const prompt = PROMPTS[visible[index] ?? index] ?? PROMPTS[0]!;
              const Icon = PROMPT_ICONS[prompt.id] ?? MessageCircleQuestion;
              return (
                <motion.div
                  key={slot.key}
                  className={cn("scene-float absolute hidden md:block", slot.position)}
                  style={{ ["--float-delay" as string]: `${slot.float}ms` }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={reduce ? { duration: 0 } : { duration: 0.32 }}
                >
                  {/* The chip itself cross-fades on its own key, inside the
                      slot that holds the position - so the rotation is a word
                      changing, never a chip flying across the screen. */}
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.span
                      key={prompt.id}
                      className="t-ui inline-flex items-center gap-sp-4 rounded-r-3 border border-stroke-subtle bg-surface-1/50 px-sp-5 py-sp-3 text-ink-4 backdrop-blur-[2px]"
                      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 6, filter: "blur(4px)" }}
                      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                      exit={reduce ? { opacity: 0 } : { opacity: 0, y: -6, filter: "blur(4px)" }}
                      transition={reduce ? { duration: 0 } : { duration: 0.42 }}
                    >
                      <Icon size={13} strokeWidth={1.5} className="shrink-0 text-ink-5" />
                      {prompt.label}
                    </motion.span>
                  </AnimatePresence>
                </motion.div>
              );
            })
          : null}
      </AnimatePresence>
    </motion.div>
  );
}
