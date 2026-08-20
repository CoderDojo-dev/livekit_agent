import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Reports whether a scroll container overflows horizontally, and which edges are still live.
 *
 * Drives the `.edge-fade-x` mask in styles.css. The distinction matters: a fade on the left edge
 * when you are already scrolled to the start is a lie about scrollability, and it clips the first
 * column's text for no reason.
 *
 * Returns "none" when everything fits, so a table that needs no scrolling gets no mask at all.
 */
export type OverflowEdges = "none" | "start" | "end" | "true";

export function useOverflowX<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [edges, setEdges] = useState<OverflowEdges>("none");

  const sync = useCallback(() => {
    const node = ref.current;
    if (!node) return;

    // 1px tolerance: sub-pixel layout rounding otherwise reports a permanent 0.5px overflow.
    const overflowing = node.scrollWidth - node.clientWidth > 1;
    if (!overflowing) {
      setEdges("none");
      return;
    }

    const atStart = node.scrollLeft <= 1;
    const atEnd = node.scrollWidth - node.clientWidth - node.scrollLeft <= 1;

    setEdges(atStart ? "start" : atEnd ? "end" : "true");
  }, []);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    sync();

    node.addEventListener("scroll", sync, { passive: true });

    /* ResizeObserver catches both viewport changes and content changes (a page swap can change
     * the widest cell, and with it whether the table overflows at all).
     *
     * Feature-detected, not assumed: jsdom does not implement ResizeObserver, and neither do
     * older browsers. Without the guard, constructing it throws inside an effect and takes down
     * every component that renders a TableShell. The fade is an enhancement — losing it must
     * never cost the table itself. */
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", sync, { passive: true });
      return () => {
        node.removeEventListener("scroll", sync);
        window.removeEventListener("resize", sync);
      };
    }

    const observer = new ResizeObserver(sync);
    observer.observe(node);
    for (const child of Array.from(node.children)) observer.observe(child);

    return () => {
      node.removeEventListener("scroll", sync);
      observer.disconnect();
    };
  }, [sync]);

  return { ref, edges, sync } as const;
}
