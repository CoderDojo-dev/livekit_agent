import { useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";

const TOKEN_URL = import.meta.env.VITE_TOKEN_URL ?? "http://localhost:8107";
const ROOM_PREFIX = import.meta.env.VITE_ROOM_PREFIX ?? "telecom-support";

type Status = "idle" | "connecting" | "connected" | "error";

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>("");
  const [events, setEvents] = useState<string[]>([]);
  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement | null>(null);

  function trace(event: string, details: Record<string, unknown> = {}) {
    const line = `${new Date().toLocaleTimeString()} ${event}`;
    setEvents((current) => [line, ...current].slice(0, 8));
    console.info("[client-widget]", event, details);
    void fetch(`${TOKEN_URL}/client-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event,
        room: typeof details.room === "string" ? details.room : undefined,
        identity: typeof details.identity === "string" ? details.identity : undefined,
        details,
      }),
    }).catch(() => undefined);
  }

  async function startCall() {
    setError("");
    setStatus("connecting");

    const startedAt = Date.now();
    const roomName = `${ROOM_PREFIX}-${startedAt}`;
    const identity = `caller-${startedAt}`;
    trace("start_call_clicked", { room: roomName, identity });

    try {
      const res = await fetch(`${TOKEN_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room: roomName,
          identity,
          name: "Caller",
        }),
      });
      if (!res.ok) throw new Error(`token-service ${res.status}`);
      const { token, url, room, agent_name } = await res.json();
      trace("token_received", { room, identity, url, agent_name });

      const livekitRoom = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = livekitRoom;

      livekitRoom.on(RoomEvent.Connected, () =>
        trace("livekit_connected", { room: roomName, identity }),
      );
      livekitRoom.on(RoomEvent.LocalTrackPublished, (publication) =>
        trace("local_track_published", { room: roomName, source: publication.source }),
      );
      livekitRoom.on(RoomEvent.ParticipantConnected, (participant) =>
        trace("participant_connected", { room: roomName, participant: participant.identity }),
      );
      livekitRoom.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        trace("remote_track_subscribed", { room: roomName, kind: track.kind });
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.autoplay = true;
          audioRef.current?.appendChild(el);
        }
      });
      livekitRoom.on(RoomEvent.Disconnected, (reason) => {
        trace("livekit_disconnected", { room: roomName, reason });
        setStatus("idle");
      });

      await livekitRoom.connect(url, token);
      await livekitRoom.localParticipant.setMicrophoneEnabled(true);
      trace("microphone_enabled", { room: roomName, identity });
      setStatus("connected");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      trace("call_error", { room: roomName, identity, message });
      setError(message);
      setStatus("error");
    }
  }

  async function endCall() {
    await roomRef.current?.disconnect();
    roomRef.current = null;
    setStatus("idle");
  }

  const connected = status === "connected";
  const busy = status === "connecting";

  return (
    <main className="widget">
      <header>
        <h1>Tunisie Telecom</h1>
        <p className="subtitle">Voice customer support</p>
      </header>

      <div className={`status status--${status}`}>
        <span className="dot" />
        {status === "idle" && "Ready to call"}
        {status === "connecting" && "Connecting..."}
        {status === "connected" && "Connected - speak now"}
        {status === "error" && `Error: ${error}`}
      </div>

      <div className="actions">
        {!connected ? (
          <button className="btn btn--call" onClick={startCall} disabled={busy}>
            {busy ? "Connecting..." : "Start call"}
          </button>
        ) : (
          <button className="btn btn--end" onClick={endCall}>
            End call
          </button>
        )}
      </div>

      <p className="hint">
        Speak in French, Arabic, or English. The assistant will greet you and route your request.
      </p>

      {events.length > 0 && (
        <ol className="events" aria-label="Call events">
          {events.map((event) => (
            <li key={event}>{event}</li>
          ))}
        </ol>
      )}

      <div ref={audioRef} hidden />
    </main>
  );
}
