import type { AgentState } from "@livekit/components-react";
import type { OrbState } from "@/lib/orb-config";

/**
 * LiveKit AgentState -> OrbState.
 *
 * The two machines are the same size (9 states); only "pre-connect-buffering"
 * is spelled differently from the orb's "preConnect". The map is exhaustive on
 * purpose: a future LiveKit state falls back to "idle" while connected and
 * "disconnected" otherwise, so the orb can never freeze on a stale frame.
 */
export function toOrbState(agentState: AgentState | undefined, connected: boolean): OrbState {
  switch (agentState) {
    case "disconnected":
      return "disconnected";
    case "connecting":
      return "connecting";
    case "pre-connect-buffering":
      return "preConnect";
    case "initializing":
      return "initializing";
    case "idle":
      return "idle";
    case "listening":
      return "listening";
    case "thinking":
      return "thinking";
    case "speaking":
      return "speaking";
    case "failed":
      return "failed";
    default:
      return connected ? "idle" : "disconnected";
  }
}
