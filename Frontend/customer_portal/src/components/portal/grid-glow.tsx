import { useEffect, useRef } from "react";

/* ---------------------------------------------------------------------------
 * components/portal/grid-glow.tsx — the cursor light.
 * A fixed, pointer-transparent layer of monochrome light that drifts toward
 * the pointer. The theme owns the gradient (--cursor-glow); this component
 * only feeds it a lerped position via --gx/--gy on a requestAnimationFrame
 * loop, so movement stays smooth even across slow frames and nothing about
 * the effect leaks into React re-renders. Fades in on the first pointer
 * move, fades out when the pointer leaves the window.
 * ------------------------------------------------------------------------- */

export function GridGlow() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const current = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    const target = { ...current };
    let raf = 0;
    let visible = false;

    const apply = (x: number, y: number) => {
      el.style.setProperty("--gx", `${x}px`);
      el.style.setProperty("--gy", `${y}px`);
    };
    apply(current.x, current.y);

    const onPointerMove = (e: PointerEvent) => {
      target.x = e.clientX;
      target.y = e.clientY;
      if (!visible) {
        visible = true;
        el.style.opacity = "1";
      }
    };

    const onPointerLeave = () => {
      visible = false;
      el.style.opacity = "0";
    };

    const tick = () => {
      const k = reduced ? 1 : 0.14;
      current.x += (target.x - current.x) * k;
      current.y += (target.y - current.y) * k;
      apply(current.x, current.y);
      raf = requestAnimationFrame(tick);
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onPointerLeave);
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointerMove);
      document.documentElement.removeEventListener("pointerleave", onPointerLeave);
    };
  }, []);

  return <div ref={ref} className="grid-cursor-glow" aria-hidden="true" />;
}
