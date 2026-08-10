import { useEffect, useRef, useState } from "react";
import { createOrbRenderer, type OrbHandle } from "./orb-renderer";
import { ORB_STATES, type OrbState } from "@/lib/orb-config";
import { cn } from "@/lib/utils";

type OrbProps = {
  state: OrbState;
  /** niveau audio 0..1, pilote l'amplitude du deplacement */
  level?: number;
  size?: number;
  className?: string;
};

/**
 * components/orb/orb.tsx — l'Orbe. Une des six exceptions au cercle interdit.
 * Repli CSS achromatique si WebGL2 est indisponible.
 */
export function Orb({ state, level = 0, size = 320, className }: OrbProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const handleRef = useRef<OrbHandle | null>(null);
  const [fallback, setFallback] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const handle = createOrbRenderer(canvas, state, reduced);
    if (!handle) {
      setFallback(true);
      return;
    }
    handleRef.current = handle;
    const onContextLost = (e: Event) => {
      e.preventDefault();
      handleRef.current?.destroy();
      handleRef.current = null;
      setFallback(true);
    };
    canvas.addEventListener("webglcontextlost", onContextLost);
    return () => {
      canvas.removeEventListener("webglcontextlost", onContextLost);
      handleRef.current?.destroy();
      handleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    handleRef.current?.setState(state);
  }, [state]);

  useEffect(() => {
    handleRef.current?.setLevel(level);
  }, [level]);

  const target = ORB_STATES[state];

  return (
    <div
      className={cn("relative select-none", className)}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      {fallback ? (
        <div
          className="h-full w-full rounded-[50%] transition-all duration-500"
          style={{
            background: `radial-gradient(circle at 38% 32%, rgba(255,255,255,${
              target.luminance * 0.9
            }) 0%, rgba(255,255,255,${target.luminance * 0.22}) 42%, rgba(255,255,255,0.02) 72%, transparent 100%)`,
            boxShadow: `0 0 ${Math.round(target.rim * 60)}px rgba(255,255,255,${
              target.luminance * 0.14
            })`,
          }}
        />
      ) : (
        <canvas ref={canvasRef} className="h-full w-full" />
      )}
    </div>
  );
}
