import { useCallback, useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useAgent, useSessionContext } from "@livekit/components-react";
import { AnimatePresence, motion } from "motion/react";
import { Mic, MicOff, PhoneCall, PhoneOff, LockKeyhole } from "lucide-react";
import { Orb } from "@/components/orb/orb";
import { OrbPlinth } from "@/components/orb/orb-plinth";
import { ORB_SIZE, type OrbState } from "@/lib/orb-config";
import { toOrbState } from "@/lib/orb-state";
import { useOrbLevel } from "@/hooks/use-orb-level";
import { useInputControls } from "@/hooks/use-input-controls";
import { useCustomerName } from "@/hooks/use-customer-name";
import { VoiceSessionProvider } from "@/components/assistant/voice-session";
import { useParticipantName } from "@/components/assistant/participant-name";
import { StartAudioButton } from "@/components/assistant/start-audio-button";
import { LiveStream } from "@/components/assistant/live-stream";
import { Button, Card, IconButton, StatusChip } from "@/components/portal/primitives";
import { T_BASE } from "@/components/portal/data";
import { duration } from "@/lib/format";
import { copy } from "@/lib/copy";
import { reportVoiceEvent } from "@/lib/api/voice.server";

export const Route = createFileRoute("/_portal/assistant")({
  head: () => ({
    meta: [
      { title: "Assistant — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Start a private, encrypted voice conversation with the Nexus assistant and see every action it takes on your account.",
      },
      { property: "og:title", content: "Assistant — Nexus Customer Portal" },
      {
        property: "og:description",
        content:
          "Private voice support that confirms before it acts, with a live transcript you can keep.",
      },
    ],
  }),
  component: AssistantScreen,
  // The LiveKit bundle is only paid for on this route.
  ssr: false,
});

function AssistantScreen() {
  // full_name from the existing profile-detail query; "You" until it resolves.
  const participantName = useCustomerName();
  return (
    <VoiceSessionProvider participantName={participantName}>
      <AssistantStage />
    </VoiceSessionProvider>
  );
}

function AssistantStage() {
  const session = useSessionContext();
  const agent = useAgent();
  const name = useParticipantName();

  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  const connected = session.isConnected;
  // connectionState is the only reliable latch: isConnected oscillates while
  // ICE settles and while the agent joins. Verified pattern from App.tsx.
  const inCall = session.connectionState !== "disconnected";

  const orbState: OrbState = toOrbState(agent.state, connected);
  const level = useOrbLevel(agent.microphoneTrack);
  const stateCopy = copy.assistant.state[orbState] ?? copy.assistant.state.disconnected;

  const start = useCallback(async () => {
    if (starting || connected) return;
    setError(null);
    setStarting(true);
    setCallId((n) => n + 1);
    void reportVoiceEvent({
      data: { event: "start_session_clicked", details: { surface: "portal" } },
    });
    try {
      await session.start({
        tracks: {
          microphone: { enabled: true, publishOptions: { preConnectBuffer: true } },
          camera: { enabled: false },
          screenShare: { enabled: false },
        },
      });
      setStartedAt(Date.now());
      void reportVoiceEvent({ data: { event: "session_started", details: { surface: "portal" } } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : copy.assistant.errors.generic);
      void reportVoiceEvent({ data: { event: "session_start_failed", details: {} } });
    } finally {
      setStarting(false);
    }
  }, [starting, connected, session]);

  const end = useCallback(async () => {
    setError(null);
    await session.end();
    void reportVoiceEvent({ data: { event: "session_ended", details: {} } });
  }, [session]);

  // Any disconnect — End, the agent's end_conversation tool deleting the room,
  // or a dropped network — clears the transient error. The visible restore is
  // already reactive through connectionState. Verified pattern from App.tsx.
  useEffect(() => {
    if (session.connectionState === "disconnected") setError(null);
  }, [session.connectionState]);

  return (
    <div className="flex min-h-[calc(100vh-8rem)] flex-col items-center justify-center gap-sp-9">
      {/* ORB — untouched component, real inputs. */}
      <div className="relative flex flex-col items-center">
        <Orb
          state={orbState}
          level={level}
          size={inCall ? ORB_SIZE.call : ORB_SIZE.rest}
          className="transition-[width,height] duration-500"
        />
        <OrbPlinth width={inCall ? ORB_SIZE.call : ORB_SIZE.rest} />
      </div>

      {/* STATE COPY — cross-faded, aria-live so it is announced once. */}
      <div className="min-h-[72px] text-center" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={orbState}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={T_BASE}
          >
            <div className="t-title-2 text-ink-1">{stateCopy.label}</div>
            <p className="t-body mt-sp-3 text-ink-4">{stateCopy.detail}</p>
          </motion.div>
        </AnimatePresence>
      </div>

      {error ? (
        <div
          role="alert"
          className="t-caption max-w-md rounded-r-3 border border-stroke-strong bg-surface-2 px-sp-6 py-sp-5 text-ink-2"
        >
          {error}
        </div>
      ) : null}

      {/* CONTROLS — Start swaps for the call bar at --z-callbar. */}
      <div className="flex min-h-14 items-center gap-sp-5">
        <AnimatePresence mode="wait" initial={false}>
          {!inCall ? (
            <motion.div
              key="start"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={T_BASE}
            >
              <Button variant="primary" size="lg" onClick={start} disabled={starting}>
                <PhoneCall size={17} strokeWidth={1.5} />
                {starting ? copy.assistant.connecting : copy.assistant.start}
              </Button>
            </motion.div>
          ) : (
            <motion.div
              key="bar"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={T_BASE}
            >
              <CallBar onEnd={end} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Browsers block autoplay until a gesture: this is how the customer
          hears the assistant. Same component the client-widget uses. */}
      <StartAudioButton label={copy.assistant.enableAudio} />

      <div className="flex items-center gap-sp-5">
        <StatusChip tone="outline">
          <LockKeyhole size={12} strokeWidth={1.5} /> {copy.assistant.assurance.encrypted}
        </StatusChip>
        <StatusChip tone="dotted">{copy.assistant.assurance.audioOnly}</StatusChip>
      </div>

      {/* LIVE STREAM — keyed on callId so each call starts with a clean stack. */}
      <LiveStream key={callId} participantName={name} />

      {/* SUMMARY — real duration, never a hardcoded string. */}
      {!inCall && startedAt ? (
        <Card className="w-full max-w-lg">
          <div className="t-micro-2 text-ink-5">{copy.assistant.summary.heading}</div>
          <div className="mt-sp-5 grid grid-cols-2 gap-sp-6">
            <MetricPair
              label={copy.assistant.summary.duration}
              value={duration((Date.now() - startedAt) / 1000)}
            />
            <MetricPair
              label={copy.assistant.summary.turns}
              value={copy.assistant.summary.turnsPending}
            />
          </div>
          <p className="t-caption mt-sp-6 text-ink-4">{copy.assistant.summary.savedNote}</p>
        </Card>
      ) : null}
    </div>
  );
}

function CallBar({ onEnd }: { onEnd: () => void }) {
  const { microphoneToggle } = useInputControls();
  const muted = !microphoneToggle.enabled;
  return (
    <div className="z-callbar flex items-center gap-sp-4 rounded-r-5 border border-stroke-default bg-surface-2 p-sp-3 shadow-elev-3">
      <IconButton
        label={muted ? copy.assistant.controls.unmute : copy.assistant.controls.mute}
        onClick={() => void microphoneToggle.toggle()}
      >
        {muted ? <MicOff size={16} strokeWidth={1.5} /> : <Mic size={16} strokeWidth={1.5} />}
      </IconButton>
      <Button variant="danger" size="sm" onClick={onEnd}>
        <PhoneOff size={15} strokeWidth={1.5} />
        {copy.assistant.end}
      </Button>
    </div>
  );
}

function MetricPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-5">
      <div className="t-micro-2 text-ink-5">{label}</div>
      <div className="t-metric-m mt-sp-3 text-ink-1">{value}</div>
    </div>
  );
}
