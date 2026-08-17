import { useEffect, useRef, useState } from "react";
import { useTrackVolume, type TrackReference } from "@livekit/components-react";

const FRAME_MS = 1000 / 30; // same 30fps commit budget as the client-widget hook

/**
 * Smoothed 0..1 level for Orb.setLevel().
 *
 * Same analyser settings as the client-widget aura hook so both surfaces react
 * identically to the same audio. Committed at 30fps instead of every analyser
 * frame, because the orb renderer reads the value on its own animation loop and
 * a 60fps React commit is wasted work.
 */
export function useOrbLevel(track: TrackReference | undefined): number {
  const volume = useTrackVolume(track as TrackReference, {
    fftSize: 256,
    smoothingTimeConstant: 0.7,
  });

  const [level, setLevel] = useState(0);
  const latest = useRef(0);
  latest.current = Number.isFinite(volume) ? Math.min(Math.max(volume, 0), 1) : 0;

  useEffect(() => {
    const id = window.setInterval(() => {
      setLevel((previous) => {
        const target = latest.current;
        // Asymmetric smoothing: rise fast so speech feels immediate, fall slow
        // so the orb does not flicker between syllables.
        const next = target > previous ? previous + (target - previous) * 0.6 : previous * 0.82;
        return Math.abs(next - previous) < 0.004 ? previous : next;
      });
    }, FRAME_MS);
    return () => window.clearInterval(id);
  }, []);

  return level;
}
