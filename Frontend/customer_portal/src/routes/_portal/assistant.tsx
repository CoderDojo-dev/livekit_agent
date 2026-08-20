import { useCallback, useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
import { usePortalSession } from "@/lib/use-portal-session";
import { isWriteTool, type ToolEvent } from "@/lib/tool-events";
import { VoiceSessionProvider } from "@/components/assistant/voice-session";
import { useParticipantName } from "@/components/assistant/participant-name";
import { StartAudioButton } from "@/components/assistant/start-audio-button";
import { LiveStream } from "@/components/assistant/live-stream";
import { Button, Card, IconButton, StatusChip } from "@/components/portal/primitives";
import { T_BASE, T_MICRO, T_PANEL, T_STAGE } from "@/components/portal/data";
import { duration } from "@/lib/format";
import { turnCount } from "@/lib/conversation";
import { brand, copy, pageTitle } from "@/lib/copy";
import { reportVoiceEvent } from "@/lib/api/voice.server";
import { fetchConversations } from "@/lib/api/activity.server";
import { qk } from "@/lib/query-keys";
import { usePortalReducedMotion } from "@/hooks/use-portal-motion";

export const Route = createFileRoute("/_portal/assistant")({
  head: () => ({
    meta: [
      { title: pageTitle("Assistant") },
      {
        name: "description",
        content:
          "Start a private, encrypted voice conversation with the assistant and see every action it takes on your account.",
      },
      { property: "og:title", content: brand.name },
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
  const portalSession = usePortalSession();
  const queryClient = useQueryClient();

  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [callId, setCallId] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [hadWriteTools, setHadWriteTools] = useState(false);

  const connected = session.isConnected;
  // connectionState is the only reliable latch: isConnected oscillates while
  // ICE settles and while the agent joins. Verified pattern from App.tsx.
  const inCall = session.connectionState !== "disconnected";

  // The two-column grid exists only from lg up. Below lg the stage and the
  // transcript stack in one scrolling column (a phone in a voice call has no
  // use for side-by-side). Mirrors Tailwind's default lg breakpoint (64rem).
  const [isLg, setIsLg] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(min-width: 64rem)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 64rem)");
    const onChange = (event: MediaQueryListEvent) => setIsLg(event.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  // Reduced motion is honoured explicitly on every JS-driven transition in
  // this scene: styles.css only covers CSS transitions, not Framer Motion.
  // The hook merges the OS media query with the portal preference.
  const reduce = usePortalReducedMotion();

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

  const handleToolEvent = useCallback((event: ToolEvent) => {
    if (isWriteTool(event.name)) setHadWriteTools(true);
  }, []);

  // Post-call reconciliation, in two tiers.
  //  - Every call, write tools or not, produced a session row: the conversation
  //    list must show it, otherwise Activity silently lags behind reality.
  //  - Only a write tool can have changed billing, requests or balances, so the
  //    broad sweep stays gated on that.
  // The worker commits after the call ends, hence the delay.
  const customerId = portalSession?.customerId;
  useEffect(() => {
    if (session.connectionState !== "disconnected" || !startedAt || !customerId) return;
    const timer = window.setTimeout(() => {
      void queryClient.invalidateQueries({ queryKey: ["me", customerId, "conversations"] });
      if (hadWriteTools) void queryClient.invalidateQueries({ queryKey: ["me", customerId] });
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [session.connectionState, startedAt, hadWriteTools, queryClient, customerId]);

  // After the call the server is the only honest source for how many turns it
  // contained: the browser never sees the persisted turn rows. Enabled only
  // once a call has finished, so an idle Assistant tab issues no requests.
  const recap = useQuery({
    queryKey: qk.conversations(customerId ?? "unknown", 1, 0),
    queryFn: () => fetchConversations({ data: { limit: 1, offset: 0 } }),
    enabled: Boolean(customerId) && !inCall && startedAt !== null,
    staleTime: 0,
    refetchInterval: (query) => (query.state.data?.items.length ? false : 2000),
  });
  const lastCall = recap.data?.items[0];

  // The stage column - the orb, its copy, and the controls. Shared verbatim by
  // both layout branches below (desktop grid track and mobile stacked column).
  const stage = (
    <>
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

      {/* Pre-call hint. The transcript column is zero-width until a call
          starts, so this lives in the stage column instead of inside
          LiveStream's pre-connect branch. */}
      <AnimatePresence initial={false}>
        {!inCall ? (
          <motion.p
            key="will-appear"
            className="t-caption text-center text-ink-5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={reduce ? { duration: 0 } : T_MICRO}
          >
            {copy.assistant.stream.willAppear}
          </motion.p>
        ) : null}
      </AnimatePresence>

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
    </>
  );

  // LIVE STREAM — keyed on callId so each call starts with a clean stack.
  const liveStream = (
    <LiveStream key={callId} participantName={name} onToolEvent={handleToolEvent} />
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      {/*
        One grid, two states. The stage column always exists; the transcript
        column is a real grid track that animates from 0fr to 1fr, so the orb
        slides left as a consequence of the track resizing rather than being
        translated by hand. That keeps the orb in normal flow - no absolute
        positioning, no transform origin to fight, and the restore on
        disconnect is the same animation run backwards.
      */}
      {isLg ? (
        <motion.div
          layout
          className="grid min-h-0 flex-1 items-center gap-sp-8 lg:gap-sp-10"
          animate={{
            gridTemplateColumns: inCall
              ? "minmax(0,0.85fr) minmax(0,1.15fr)"
              : "minmax(0,1fr) minmax(0,0fr)",
          }}
          transition={reduce ? { duration: 0 } : T_STAGE}
        >
          {/* Column 1 - the stage: orb, state copy, controls. Always mounted. */}
          <motion.div layout className="flex min-h-0 flex-col items-center justify-center gap-sp-7">
            {stage}
          </motion.div>

          {/* Column 2 - the transcript. Overflow lives here and nowhere else. */}
          <div className="flex h-full min-h-0 items-center justify-center overflow-hidden">
            <AnimatePresence initial={false}>
              {inCall ? (
                <motion.div
                  key="transcript"
                  className="flex h-full max-h-full min-h-0 w-full flex-col overflow-y-auto"
                  initial={{ opacity: 0, x: 12 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 12 }}
                  transition={reduce ? { duration: 0 } : T_PANEL}
                >
                  {liveStream}
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </motion.div>
      ) : (
        // Below lg: plain stacked column. The whole thing scrolls as one
        // region; pb-20 clears the mobile tabbar, lg:pb-0 is a no-op here.
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-sp-7 overflow-y-auto pb-20 lg:pb-0">
          {stage}
          {inCall ? liveStream : null}
        </div>
      )}

      {/* SUMMARY — real duration from server, real turn count from recap query.
          Stays below the stage, outside the grid. */}
      {!inCall && startedAt ? (
        <Card className="w-full max-w-lg">
          <div className="t-micro-2 text-ink-5">{copy.assistant.summary.heading}</div>
          <div className="mt-sp-5 grid grid-cols-2 gap-sp-6">
            <MetricPair
              label={copy.assistant.summary.duration}
              value={
                lastCall?.duration_seconds != null
                  ? duration(lastCall.duration_seconds)
                  : duration((Date.now() - startedAt) / 1000)
              }
            />
            <MetricPair
              label={copy.assistant.summary.turns}
              value={
                lastCall ? String(turnCount(lastCall.turns)) : copy.assistant.summary.turnsPending
              }
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
