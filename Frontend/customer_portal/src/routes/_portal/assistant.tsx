import { useCallback, useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Mic, MicOff, Captions, Keyboard, Volume2, Lock, Radio } from "lucide-react";
import { Orb } from "@/components/orb/orb";
import { OrbPlinth } from "@/components/orb/orb-plinth";
import { ORB_SIZE, type OrbState } from "@/lib/orb-config";
import { copy } from "@/lib/copy";
import { Button, Card, Divider, IconButton, SectionLabel, StatusChip } from "@/components/portal/primitives";
import { interactions } from "@/lib/fixtures/interactions";
import { cn } from "@/lib/utils";

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
  component: AssistantScene,
});

type Turn = { speaker: "assistant" | "you"; text: string; at: string };

const SCRIPT: readonly Turn[] = interactions[0]!.transcript.map((t) => ({
  speaker: t.speaker === "specialist" ? "assistant" : t.speaker,
  text: t.text,
  at: t.at,
}));

const ACTIVE: readonly OrbState[] = ["listening", "thinking", "speaking"];

function AssistantScene() {
  const [state, setState] = useState<OrbState>("disconnected");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [ended, setEnded] = useState(false);
  const [muted, setMuted] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [level, setLevel] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clear = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  }, []);

  useEffect(() => clear, [clear]);

  useEffect(() => {
    if (!ACTIVE.includes(state)) {
      setLevel(0);
      return;
    }
    const id = setInterval(() => {
      setLevel(state === "thinking" ? 0.2 : 0.25 + Math.random() * 0.65);
    }, 140);
    return () => clearInterval(id);
  }, [state]);

  const at = (ms: number, fn: () => void) => {
    timers.current.push(setTimeout(fn, ms));
  };

  function start() {
    clear();
    setEnded(false);
    setTurns([]);
    setState("connecting");
    at(900, () => setState("preConnect"));
    at(1700, () => setState("initializing"));
    at(2500, () => setState("idle"));
    let t = 3200;
    SCRIPT.forEach((turn, i) => {
      const speaking = turn.speaker === "assistant";
      at(t, () => setState(speaking ? "thinking" : "listening"));
      at(t + (speaking ? 900 : 500), () => {
        if (speaking) setState("speaking");
        setTurns((prev) => [...prev, turn]);
      });
      t += 2600 + turn.text.length * 12;
      if (i === SCRIPT.length - 1) at(t, () => setState("idle"));
    });
  }

  function end() {
    clear();
    setState("disconnected");
    setEnded(true);
  }

  const live = state !== "disconnected";
  const s = copy.assistant.state[state];
  const size = live ? ORB_SIZE.call : ORB_SIZE.rest;

  return (
    <div className="grid gap-sp-9 lg:grid-cols-[minmax(0,1fr)_380px]">
      {/* --- la scene ------------------------------------------------------ */}
      <section className="flex min-h-[560px] flex-col items-center justify-center py-sp-10">
        <div className="flex flex-col items-center">
          <Orb
            state={state}
            level={level}
            size={size}
            className="transition-[width,height] duration-500"
          />
          <OrbPlinth width={size} className="-mt-sp-8" />
        </div>

        <div className="mt-sp-10 max-w-md text-center">
          {!live && !ended ? (
            <h2 className="t-display text-ink-1">{copy.assistant.title}</h2>
          ) : (
            <div className="t-title-2 text-ink-1">{s.label}</div>
          )}
          <p className="t-body mt-sp-4 text-ink-4">{s.detail}</p>
        </div>

        <div className="mt-sp-9 flex items-center gap-sp-5">
          {!live ? (
            <Button variant="primary" size="lg" onClick={start}>
              {copy.assistant.start}
            </Button>
          ) : (
            <>
              <IconButton
                label={muted ? copy.assistant.controls.unmute : copy.assistant.controls.mute}
                onClick={() => setMuted((v) => !v)}
                className={cn(
                  "h-11 w-11 border border-stroke-default bg-surface-2",
                  muted && "bg-surface-4 text-ink-1",
                )}
              >
                {muted ? <MicOff size={17} strokeWidth={1.5} /> : <Mic size={17} strokeWidth={1.5} />}
              </IconButton>
              <IconButton
                label={copy.assistant.controls.captions}
                onClick={() => setCaptions((v) => !v)}
                className={cn(
                  "h-11 w-11 border border-stroke-default bg-surface-2",
                  captions && "bg-surface-4 text-ink-1",
                )}
              >
                <Captions size={17} strokeWidth={1.5} />
              </IconButton>
              <Button variant="danger" size="lg" onClick={end}>
                {copy.assistant.end}
              </Button>
              <IconButton
                label={copy.assistant.controls.volume}
                className="h-11 w-11 border border-stroke-default bg-surface-2"
              >
                <Volume2 size={17} strokeWidth={1.5} />
              </IconButton>
              <IconButton
                label={copy.assistant.controls.keyboard}
                className="h-11 w-11 border border-stroke-default bg-surface-2"
              >
                <Keyboard size={17} strokeWidth={1.5} />
              </IconButton>
            </>
          )}
        </div>

        <div className="t-micro mt-sp-8 flex items-center gap-sp-6 text-ink-5">
          <span className="inline-flex items-center gap-sp-3">
            <Lock size={11} strokeWidth={1.5} />
            {copy.assistant.assurance.encrypted}
          </span>
          <span className="inline-flex items-center gap-sp-3">
            <Radio size={11} strokeWidth={1.5} />
            {copy.assistant.assurance.audioOnly}
          </span>
        </div>
      </section>

      {/* --- le flux ------------------------------------------------------- */}
      <aside className="lg:sticky lg:top-24 lg:self-start">
        {ended ? (
          <Card className="p-sp-7">
            <SectionLabel>{copy.assistant.summary.heading}</SectionLabel>
            <div className="mt-sp-7 grid grid-cols-3 gap-sp-5">
              {[
                [copy.assistant.summary.duration, "4m 18s"],
                [copy.assistant.summary.turns, String(SCRIPT.length)],
                [copy.assistant.summary.actions, "2"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-r-3 border border-stroke-subtle bg-surface-2 p-sp-5">
                  <div className="t-micro-2 text-ink-5">{k}</div>
                  <div className="t-metric-m mt-sp-3 text-ink-1">{v}</div>
                </div>
              ))}
            </div>
            <Divider className="my-sp-7" />
            <div className="t-micro text-ink-4">{copy.assistant.summary.changed}</div>
            <p className="t-body mt-sp-4 text-ink-3">
              {copy.assistant.summary.nothingChanged}
            </p>
            <div className="mt-sp-8 flex gap-sp-4">
              <Button variant="secondary" size="sm">
                {copy.assistant.summary.download}
              </Button>
              <Button variant="quiet" size="sm" onClick={start}>
                {copy.assistant.summary.resume}
              </Button>
            </div>
          </Card>
        ) : (
          <Card className="flex h-[560px] flex-col p-sp-0" inset={false}>
            <div className="flex items-center justify-between border-b border-stroke-subtle px-sp-6 py-sp-5">
              <span className="t-micro text-ink-4">{copy.assistant.stream.heading}</span>
              <StatusChip tone={live ? "solid" : "muted"}>
                {live ? "LIVE" : "IDLE"}
              </StatusChip>
            </div>
            <div className="flex-1 space-y-sp-7 overflow-y-auto px-sp-6 py-sp-6">
              {turns.length === 0 ? (
                <p className="t-caption text-ink-5">
                  {live ? copy.assistant.state.idle.detail : copy.empty.generic}
                </p>
              ) : (
                turns.map((turn, i) => (
                  <div key={i}>
                    <div className="t-micro-2 mb-sp-3 flex items-center gap-sp-4 text-ink-5">
                      <span>
                        {turn.speaker === "assistant"
                          ? copy.assistant.stream.assistant
                          : copy.assistant.stream.you}
                      </span>
                      <span className="t-mono-s">{turn.at}</span>
                    </div>
                    <p
                      className={cn(
                        "t-body",
                        turn.speaker === "assistant" ? "text-ink-1" : "text-ink-3",
                      )}
                    >
                      {turn.text}
                    </p>
                  </div>
                ))
              )}
            </div>
            <div className="border-t border-stroke-subtle p-sp-5">
              <input
                placeholder={copy.assistant.stream.composer}
                className="focus-ring t-ui-regular h-9 w-full rounded-r-2 border border-stroke-default bg-surface-2 px-sp-5 text-ink-1 placeholder:text-ink-5"
              />
            </div>
          </Card>
        )}
      </aside>
    </div>
  );
}
