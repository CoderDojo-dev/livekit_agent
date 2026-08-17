import {
  SessionProvider,
  type UseSessionReturn,
  RoomAudioRenderer,
  type SessionProviderProps,
  type RoomAudioRendererProps,
} from "@livekit/components-react";
import type { ReactNode } from "react";
import { Room } from "livekit-client";

/**
 * Port of apps/client-widget/src/components/agents-ui/agent-session-provider.tsx:
 * SessionProvider plus RoomAudioRenderer for audio playback.
 */
export type AgentSessionProviderProps = SessionProviderProps &
  RoomAudioRendererProps & {
    room?: Room;
    volume?: number;
    muted?: boolean;
    session: UseSessionReturn;
    children: ReactNode;
  };

export function AgentSessionProvider({
  session,
  children,
  ...roomAudioRendererProps
}: AgentSessionProviderProps) {
  return (
    <SessionProvider session={session}>
      {children}
      <RoomAudioRenderer {...roomAudioRendererProps} />
    </SessionProvider>
  );
}
