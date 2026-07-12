import { useCallback, useMemo, useState } from "react";
import {
  useAgent,
  useSession,
  useSessionContext,
} from "@livekit/components-react";
import { Headphones, Languages, LockKeyhole, Mic, PhoneCall } from "lucide-react";
import { TokenSource } from "livekit-client";

import { AgentAudioVisualizerAura } from "@/components/agents-ui/agent-audio-visualizer-aura";
import { AgentControlBar } from "@/components/agents-ui/agent-control-bar";
import { AgentSessionProvider } from "@/components/agents-ui/agent-session-provider";
import { StartAudioButton } from "@/components/agents-ui/start-audio-button";
import { Button } from "@/components/ui/button";

const TOKEN_SERVICE_URL = (
  import.meta.env.VITE_TOKEN_URL ?? "http://localhost:8107"
).replace(/\/$/, "");
const ROOM_PREFIX = import.meta.env.VITE_ROOM_PREFIX ?? "telecom-support";

type TokenResponse = {
  token: string;
  url: string;
  room: string;
  agent_name?: string | null;
};

function uniqueId(prefix: string) {
  const suffix =
    typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `${prefix}-${suffix}`;
}

async function reportClientEvent(
  event: string,
  details: Record<string, unknown> = {},
) {
  try {
    await fetch(`${TOKEN_SERVICE_URL}/client-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, details }),
      keepalive: true,
    });
  } catch {
    // Observability must never block the call path.
  }
}

function createExistingTokenServiceSource() {
  return TokenSource.custom(async (options) => {
    const room = uniqueId(options.roomName || ROOM_PREFIX);
    const identity = uniqueId(options.participantIdentity || "caller");

    const response = await fetch(`${TOKEN_SERVICE_URL}/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        room,
        identity,
        name: options.participantName || "Caller",
      }),
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(
        `Token service returned ${response.status}${body ? `: ${body}` : ""}`,
      );
    }

    const payload = (await response.json()) as TokenResponse;
    if (!payload.token || !payload.url) {
      throw new Error("Token service response is missing token or url");
    }

    void reportClientEvent("token_received", {
      room: payload.room,
      agent_name: payload.agent_name,
    });

    return {
      serverUrl: payload.url,
      participantToken: payload.token,
    };
  });
}

const STATE_COPY = {
  disconnected: {
    label: "Ready when you are",
    detail: "Private voice support in French, Arabic, or English.",
  },
  connecting: {
    label: "Opening a secure line",
    detail: "Connecting you to the telecom assistant.",
  },
  "pre-connect-buffering": {
    label: "Preparing your microphone",
    detail: "You can begin speaking as soon as the assistant joins.",
  },
  initializing: {
    label: "Assistant is joining",
    detail: "Loading your secure support session.",
  },
  idle: {
    label: "Assistant is ready",
    detail: "Speak naturally when you are ready.",
  },
  listening: {
    label: "Listening",
    detail: "Go ahead, the assistant can hear you.",
  },
  thinking: {
    label: "Working on it",
    detail: "Checking the right service and policy.",
  },
  speaking: {
    label: "Assistant is speaking",
    detail: "You can interrupt naturally at any time.",
  },
  failed: {
    label: "Connection needs attention",
    detail: "End the session and try again.",
  },
} as const;

function VoiceExperience() {
  const session = useSessionContext();
  const agent = useAgent();
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const copy = STATE_COPY[agent.state] ?? STATE_COPY.disconnected;

  const startSession = useCallback(async () => {
    if (isStarting || session.isConnected) return;

    setError(null);
    setIsStarting(true);
    void reportClientEvent("start_session_clicked", { audio_only: true });

    try {
      await session.start({
        tracks: {
          microphone: {
            enabled: true,
            publishOptions: { preConnectBuffer: true },
          },
          camera: { enabled: false },
          screenShare: { enabled: false },
        },
      });
      void reportClientEvent("session_started", { audio_only: true });
    } catch (cause) {
      const message =
        cause instanceof Error ? cause.message : "Unable to start the voice session";
      setError(message);
      void reportClientEvent("session_start_failed", { message });
    } finally {
      setIsStarting(false);
    }
  }, [isStarting, session]);

  const endSession = useCallback(async () => {
    setError(null);
    await session.end();
    void reportClientEvent("session_ended");
  }, [session]);

  const connected = session.isConnected;
  const pending = isStarting || agent.isPending;

  return (
    <main className="relative min-h-svh overflow-hidden bg-background text-foreground">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,oklch(0.29_0.08_220)_0%,oklch(0.16_0.025_250)_35%,oklch(0.11_0.012_255)_72%)]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,oklch(0.78_0.13_210),transparent)] opacity-60" />

      <div className="relative mx-auto flex min-h-svh w-full max-w-6xl flex-col px-5 py-6 sm:px-8 sm:py-8 lg:px-12">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid size-10 place-items-center rounded-xl border border-border bg-card text-primary shadow-sm">
              <Headphones className="size-5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight">Telecom Assist</p>
              <p className="text-xs text-muted-foreground">Customer voice support</p>
            </div>
          </div>

          <div className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-2 text-xs text-muted-foreground">
            <LockKeyhole className="size-3.5 text-primary" aria-hidden="true" />
            Secure session
          </div>
        </header>

        <section className="flex flex-1 flex-col items-center justify-center py-10 text-center sm:py-14">
          <div className="relative grid min-h-[19rem] w-full place-items-center sm:min-h-[25rem]">
            <div className="absolute size-56 rounded-full bg-primary opacity-10 blur-3xl sm:size-72" />
            <AgentAudioVisualizerAura
              size="xl"
              state={agent.state}
              color="#27d3f2"
              colorShift={0.12}
              themeMode="dark"
              audioTrack={agent.microphoneTrack}
              className="relative z-10 scale-110 sm:scale-125"
              aria-label={`Assistant state: ${copy.label}`}
            />
          </div>

          <div className="mt-2 flex max-w-xl flex-col items-center gap-3" aria-live="polite">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.14em] text-primary">
              <span
                className={`size-1.5 rounded-full ${
                  connected ? "bg-emerald-400" : pending ? "bg-amber-300" : "bg-primary"
                }`}
              />
              {copy.label}
            </div>
            <h1 className="max-w-[18ch] text-balance text-3xl font-semibold tracking-[-0.035em] sm:text-5xl">
              Voice support without the phone-tree runaround.
            </h1>
            <p className="max-w-[52ch] text-pretty text-base leading-7 text-muted-foreground">
              {copy.detail}
            </p>
          </div>

          {error && (
            <div
              role="alert"
              className="mt-6 max-w-lg rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive-foreground"
            >
              {error}
            </div>
          )}

          <div className="mt-8 flex min-h-14 items-center justify-center">
            {!connected ? (
              <Button
                size="lg"
                onClick={startSession}
                disabled={isStarting}
                className="h-14 min-w-48 rounded-full px-7 text-base font-semibold shadow-[0_12px_40px_oklch(0.72_0.15_210/0.18)] transition-transform duration-150 active:scale-[0.98]"
              >
                <PhoneCall className="size-5" aria-hidden="true" />
                {isStarting ? "Connecting..." : "Start voice session"}
              </Button>
            ) : (
              <AgentControlBar
                variant="livekit"
                controls={{
                  microphone: true,
                  camera: false,
                  screenShare: false,
                  chat: false,
                  leave: true,
                }}
                isConnected={connected}
                isChatOpen={false}
                onDisconnect={endSession}
                onDeviceError={({ error: deviceError }) => {
                  setError(deviceError.message);
                  void reportClientEvent("media_device_error", {
                    message: deviceError.message,
                  });
                }}
                className="rounded-full border border-border bg-card p-2 shadow-lg"
              />
            )}
          </div>

          <StartAudioButton
            label="Enable assistant audio"
            variant="outline"
            className="mt-4 rounded-full"
          />
        </section>

        <footer className="flex flex-col items-center justify-between gap-4 border-t border-border pt-5 text-xs text-muted-foreground sm:flex-row">
          <div className="flex items-center gap-2">
            <Mic className="size-3.5" aria-hidden="true" />
            Audio only. Camera and screen sharing are disabled.
          </div>
          <div className="flex items-center gap-2">
            <Languages className="size-3.5" aria-hidden="true" />
            Français · العربية · English
          </div>
        </footer>
      </div>
    </main>
  );
}

export default function App() {
  const tokenSource = useMemo(createExistingTokenServiceSource, []);
  const session = useSession(tokenSource, {
    roomName: ROOM_PREFIX,
    participantName: "Caller",
    agentConnectTimeoutMilliseconds: 30_000,
  });

  return (
    <AgentSessionProvider session={session} volume={1} muted={false}>
      <VoiceExperience />
    </AgentSessionProvider>
  );
}
