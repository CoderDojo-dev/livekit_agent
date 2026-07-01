import { useRef, useState } from "react";
import { Room, RoomEvent, Track, type RemoteTrack } from "livekit-client";

const TOKEN_URL = import.meta.env.VITE_TOKEN_URL ?? "http://localhost:8107";

type Status = "idle" | "connecting" | "connected" | "error";

export default function App() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string>("");
  const roomRef = useRef<Room | null>(null);
  const audioRef = useRef<HTMLDivElement | null>(null);

  async function startCall() {
    setError("");
    setStatus("connecting");
    try {
      const res = await fetch(`${TOKEN_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          room: "telecom-support",
          identity: `caller-${Date.now()}`,
          name: "Caller",
        }),
      });
      if (!res.ok) throw new Error(`token-service ${res.status}`);
      const { token, url } = await res.json();

      const room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;

      room.on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === Track.Kind.Audio) {
          const el = track.attach();
          el.autoplay = true;
          audioRef.current?.appendChild(el);
        }
      });
      room.on(RoomEvent.Disconnected, () => setStatus("idle"));

      await room.connect(url, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setStatus("connected");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
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
        {status === "connecting" && "Connecting…"}
        {status === "connected" && "Connected — speak now"}
        {status === "error" && `Error: ${error}`}
      </div>

      <div className="actions">
        {!connected ? (
          <button className="btn btn--call" onClick={startCall} disabled={busy}>
            {busy ? "Connecting…" : "Start call"}
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

      <div ref={audioRef} hidden />
    </main>
  );
}