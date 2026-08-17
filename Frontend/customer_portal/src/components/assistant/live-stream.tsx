import { useEffect, useMemo } from "react";
import {
  useAgent,
  useSessionContext,
  useTextStream,
  useTranscriptions,
} from "@livekit/components-react";
import { AnimatePresence, motion } from "motion/react";
import { LoaderCircle } from "lucide-react";

import { toOrbState } from "@/lib/orb-state";
import {
  parseToolEvent,
  timestampMs,
  toolEventText,
  isWriteTool,
  type ToolEvent,
} from "@/lib/tool-events";
import { T_BASE, T_MICRO } from "@/components/portal/data";
import { ToolEventRow } from "@/components/assistant/tool-event-row";
import { WorkingIndicator } from "@/components/assistant/working-indicator";
import { copy } from "@/lib/copy";

/*
 * Port of apps/client-widget/src/components/app/live-conversation.tsx.
 * The behaviour (new messages fade in, older ones fade out, tool calls in
 * real time, customer and agent names visible) is already solved there; this
 * file keeps the logic and swaps the external stylesheet for portal tokens.
 *
 * Tool events are intentionally separate from transcripts. The topic carries
 * only safe display metadata; the full durable transcript lives in PostgreSQL
 * via ConversationWriter. This UI is a window, not a store — deliberately
 * ephemeral.
 */
const TOOL_EVENT_TOPIC = "telecom.tool-events";
const MAX_VISIBLE_ITEMS = 3;

type StreamItem = {
  id: string;
  role: "caller" | "agent" | "tool";
  text: string;
  timestamp: number;
  partial?: boolean;
  status?: "done" | "error";
  persona?: string | null;
  name?: string;
};

export function LiveStream({
  participantName,
  onToolEvent,
}: {
  participantName: string;
  onToolEvent?: (event: ToolEvent) => void;
}) {
  const session = useSessionContext();
  const agent = useAgent();

  /*
   * useTranscriptions consumes lk.transcription text streams.
   * Interim and final streams share lk.segment_id, allowing cumulative
   * partial text to update the same visual turn instead of creating duplicates.
   */
  const transcriptions = useTranscriptions({ room: session.room });

  const { textStreams: toolStreams } = useTextStream(TOOL_EVENT_TOPIC, {
    room: session.room,
  });

  // Report tool events to the parent (e.g. so it knows a write tool ran and
  // activity should be refetched after the call).
  useEffect(() => {
    if (!onToolEvent) return;
    for (const stream of toolStreams) {
      const event = parseToolEvent(stream.text);
      if (event) onToolEvent(event);
    }
  }, [toolStreams, onToolEvent]);

  const items = useMemo(() => {
    const transcriptBySegment = new Map<string, StreamItem>();
    const localIdentity = session.room.localParticipant.identity;

    for (const stream of transcriptions) {
      const attributes = stream.streamInfo.attributes ?? {};
      const segmentId =
        attributes["lk.segment_id"] ||
        attributes["lk.transcribed_track_id"] ||
        stream.streamInfo.id;
      const isFinal = attributes["lk.transcription_final"] === "true";
      const text = stream.text.trim();
      if (!text) continue;

      const item: StreamItem = {
        id: ["transcript", stream.participantInfo.identity, segmentId].join(":"),
        role: stream.participantInfo.identity === localIdentity ? "caller" : "agent",
        text,
        timestamp: timestampMs(stream.streamInfo.timestamp),
        partial: !isFinal,
      };

      const current = transcriptBySegment.get(item.id);
      // Interim streams update continuously; final streams always replace.
      if (!current || isFinal || item.text.length >= current.text.length) {
        transcriptBySegment.set(item.id, item);
      }
    }

    const toolItems: StreamItem[] = toolStreams.flatMap((stream) => {
      const event = parseToolEvent(stream.text);
      if (!event) return [];
      return [
        {
          id: `tool:${event.id}`,
          role: "tool" as const,
          name: event.name,
          text: toolEventText(event),
          status: event.status,
          timestamp: timestampMs(event.created_at || stream.streamInfo.timestamp),
        },
      ];
    });

    /*
     * Keep only the latest three visual events. AnimatePresence fades older
     * events out when new ones arrive.
     */
    return [...transcriptBySegment.values(), ...toolItems]
      .sort((left, right) => left.timestamp - right.timestamp)
      .slice(-MAX_VISIBLE_ITEMS);
  }, [session.room, transcriptions, toolStreams]);

  if (!session.isConnected && items.length === 0) {
    return (
      <p className="t-caption text-ink-5" aria-hidden="true">
        {copy.assistant.stream.willAppear}
      </p>
    );
  }

  return (
    <section
      aria-label={copy.assistant.stream.heading}
      aria-live="polite"
      aria-atomic="false"
      className="w-full max-w-2xl"
    >
      <div className="mb-sp-4 flex items-center justify-between">
        <span className="t-micro-2 text-ink-5">{copy.assistant.stream.heading}</span>
        <span className="t-micro-2 text-ink-5">
          {copy.assistant.state[toOrbState(agent.state, session.isConnected)].label}
        </span>
      </div>

      <div className="flex flex-col gap-sp-4">
        <WorkingIndicator active={agent.state === "thinking"} />

        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item, index) => {
            const depth = items.length - 1 - index;
            const opacity = depth === 0 ? 1 : depth === 1 ? 0.52 : 0.22;
            const scale = depth === 0 ? 1 : depth === 1 ? 0.985 : 0.97;
            return (
              <motion.article
                key={item.id}
                layout="position"
                data-depth={depth}
                initial={{ opacity: 0, y: 10, scale: 0.985 }}
                animate={{ opacity, y: 0, scale }}
                exit={{ opacity: 0, y: -8, scale: 0.96 }}
                transition={T_BASE}
                className="rounded-r-4 border border-stroke-subtle bg-surface-2 px-sp-6 py-sp-5"
              >
                {item.role === "tool" ? (
                  <ToolEventRow
                    name={item.name ?? ""}
                    text={item.text}
                    status={item.status ?? "done"}
                  />
                ) : (
                  <>
                    <div className="t-micro-2 text-ink-5">
                      {item.role === "caller"
                        ? participantName
                        : (item.persona ?? copy.assistant.stream.assistant)}
                    </div>
                    <p dir="auto" className="t-body mt-sp-2 text-ink-1">
                      {item.text}
                      {item.partial && depth === 0 ? (
                        <span className="assistant-caret" aria-hidden="true" />
                      ) : null}
                    </p>
                  </>
                )}
              </motion.article>
            );
          })}
        </AnimatePresence>

        {items.length === 0 && session.isConnected ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={T_MICRO}
            className="flex items-center gap-sp-3 text-ink-5"
          >
            <LoaderCircle size={14} strokeWidth={1.5} aria-hidden="true" />
            <span className="t-caption">{copy.assistant.stream.waiting}</span>
          </motion.div>
        ) : null}
      </div>
    </section>
  );
}
