import { useMemo, type ReactNode } from "react";
import { TokenSource } from "livekit-client";
import { useSession } from "@livekit/components-react";
import { AgentSessionProvider } from "@/components/assistant/agent-session-provider";
import { ParticipantNameProvider } from "@/components/assistant/participant-name";
import { createVoiceGrant, reportVoiceEvent } from "@/lib/api/voice.server";

/**
 * Wraps the LiveKit session for the portal.
 *
 * Same shape as apps/client-widget/src/App.tsx, with one difference that matters:
 * the token comes from our own server function, so the room name and the
 * participant identity are derived from the signed session cookie instead of
 * being generated in the browser.
 */
export function VoiceSessionProvider({
  participantName,
  children,
}: {
  participantName: string;
  children: ReactNode;
}) {
  const tokenSource = useMemo(
    () =>
      TokenSource.custom(async () => {
        const grant = await createVoiceGrant();
        void reportVoiceEvent({ data: { event: "token_received", details: { room: grant.room } } });
        return { serverUrl: grant.url, participantToken: grant.token };
      }),
    [],
  );

  const session = useSession(tokenSource, {
    // The real room and identity are decided server-side; these are only the
    // hints TokenSource passes back to us, and we ignore them there.
    roomName: "portal",
    participantName,
    agentConnectTimeoutMilliseconds: 30_000,
  });

  return (
    <ParticipantNameProvider value={participantName}>
      <AgentSessionProvider session={session} volume={1} muted={false}>
        {children}
      </AgentSessionProvider>
    </ParticipantNameProvider>
  );
}
