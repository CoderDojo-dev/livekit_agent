import { useMemo } from "react";
import {
  useAgent,
  useSessionContext,
  useTextStream,
  useTranscriptions,
} from "@livekit/components-react";
import {
  AnimatePresence,
  motion,
} from "motion/react";
import {
  Check,
  LoaderCircle,
  Wrench,
  X,
} from "lucide-react";


const TOOL_EVENT_TOPIC = "telecom.tool-events";
const MAX_VISIBLE_ITEMS = 3;

type ConversationRole =
  | "caller"
  | "agent"
  | "tool";

type ConversationItem = {
  id: string;
  role: ConversationRole;
  text: string;
  timestamp: number;
  partial?: boolean;
  status?: "done" | "error";
};

type ToolEvent = {
  version: 1;
  kind: "tool";
  id: string;
  name: string;
  label: string;
  status: "done" | "error";
  created_at: number;
};


function parseToolEvent(
  text: string,
): ToolEvent | null {
  try {
    const value = JSON.parse(
      text,
    ) as Partial<ToolEvent>;

    if (
      value.version !== 1
      || value.kind !== "tool"
      || typeof value.id !== "string"
      || typeof value.name !== "string"
      || typeof value.label !== "string"
      || (
        value.status !== "done"
        && value.status !== "error"
      )
    ) {
      return null;
    }

    return value as ToolEvent;
  } catch {
    return null;
  }
}


function timestampMs(
  value: number | Date | undefined,
): number {
  if (value instanceof Date) {
    return value.getTime();
  }

  if (typeof value !== "number") {
    return Date.now();
  }

  // LiveKit timestamps can be seconds or milliseconds.
  return value < 10_000_000_000
    ? value * 1000
    : value;
}


export function LiveConversation() {
  const session = useSessionContext();
  const agent = useAgent();

  /*
   * useTranscriptions consumes lk.transcription text streams.
   * Interim and final streams share lk.segment_id, allowing cumulative
   * partial text to update the same visual turn instead of creating duplicates.
   */
  const transcriptions = useTranscriptions({
    room: session.room,
  });

  /*
   * Tool events are intentionally separate from transcripts.
   * This topic carries only safe display metadata.
   */
  const {
    textStreams: toolStreams,
  } = useTextStream(
    TOOL_EVENT_TOPIC,
    {
      room: session.room,
    },
  );

  const items = useMemo(() => {
    const transcriptBySegment =
      new Map<string, ConversationItem>();

    const localIdentity =
      session.room.localParticipant.identity;

    for (const stream of transcriptions) {
      const attributes =
        stream.streamInfo.attributes ?? {};

      const segmentId =
        attributes["lk.segment_id"]
        || attributes["lk.transcribed_track_id"]
        || stream.streamInfo.id;

      const isFinal =
        attributes["lk.transcription_final"]
        === "true";

      const text = stream.text.trim();

      if (!text) {
        continue;
      }

      const item: ConversationItem = {
        id: [
          "transcript",
          stream.participantInfo.identity,
          segmentId,
        ].join(":"),
        role:
          stream.participantInfo.identity
          === localIdentity
            ? "caller"
            : "agent",
        text,
        timestamp: timestampMs(
          stream.streamInfo.timestamp,
        ),
        partial: !isFinal,
      };

      const current =
        transcriptBySegment.get(item.id);

      /*
       * Interim streams update continuously.
       * Final streams always replace the interim representation.
       */
      if (
        !current
        || isFinal
        || item.text.length
          >= current.text.length
      ) {
        transcriptBySegment.set(
          item.id,
          item,
        );
      }
    }

    const toolItems: ConversationItem[] =
      toolStreams.flatMap((stream) => {
        const event =
          parseToolEvent(stream.text);

        if (!event) {
          return [];
        }

        return [
          {
            id: `tool:${event.id}`,
            role: "tool" as const,
            text: event.label,
            status: event.status,
            timestamp: timestampMs(
              event.created_at
              || stream.streamInfo.timestamp,
            ),
          },
        ];
      });

    /*
     * Keep only the latest three visual events.
     * AnimatePresence fades and removes older events when new events arrive.
     * The full durable transcript remains in PostgreSQL through the existing
     * ConversationWriter. This UI is deliberately ephemeral.
     */
    return [
      ...transcriptBySegment.values(),
      ...toolItems,
    ]
      .sort(
        (left, right) =>
          left.timestamp - right.timestamp,
      )
      .slice(-MAX_VISIBLE_ITEMS);
  }, [
    session.room,
    transcriptions,
    toolStreams,
  ]);

  if (
    !session.isConnected
    && items.length === 0
  ) {
    return (
      <aside
        className={[
          "live-conversation",
          "live-conversation--empty",
        ].join(" ")}
        aria-hidden="true"
      >
        <span className="live-conversation__eyebrow">
          Live conversation
        </span>

        <p>
          Your conversation will appear here
          as you speak.
        </p>
      </aside>
    );
  }

  return (
    <aside
      className="live-conversation"
      aria-label="Live conversation"
      aria-live="polite"
      aria-atomic="false"
    >
      <div className="live-conversation__heading">
        <span className="live-conversation__eyebrow">
          Live conversation
        </span>

        <span className="live-conversation__state">
          {agent.state === "thinking"
            ? "Working"
            : agent.state}
        </span>
      </div>

      <div className="live-conversation__stack">
        <AnimatePresence
          initial={false}
          mode="popLayout"
        >
          {items.map((item, index) => {
            const depth =
              items.length - 1 - index;

            const opacity =
              depth === 0
                ? 1
                : depth === 1
                  ? 0.52
                  : 0.22;

            const scale =
              depth === 0
                ? 1
                : depth === 1
                  ? 0.985
                  : 0.97;

            return (
              <motion.article
                layout="position"
                key={item.id}
                className={[
                  "live-turn",
                  `live-turn--${item.role}`,
                ].join(" ")}
                data-depth={depth}
                initial={{
                  opacity: 0,
                  x: 28,
                  scale: 0.985,
                }}
                animate={{
                  opacity,
                  x: 0,
                  scale,
                }}
                exit={{
                  opacity: 0,
                  x: 34,
                  scale: 0.96,
                }}
                transition={{
                  duration: 0.32,
                  ease: [0.16, 1, 0.3, 1],
                }}
              >
                {item.role === "tool" ? (
                  <>
                    <span
                      className="live-turn__tool-icon"
                      aria-hidden="true"
                    >
                      <Wrench />
                    </span>

                    <div className="live-turn__content">
                      <span className="live-turn__role">
                        Service action
                      </span>

                      <p dir="auto">
                        {item.text}
                      </p>
                    </div>

                    <span
                      className={[
                        "live-turn__tool-status",
                        `live-turn__tool-status--${item.status}`,
                      ].join(" ")}
                      aria-label={
                        item.status === "done"
                          ? "Completed"
                          : "Failed"
                      }
                    >
                      {item.status === "done"
                        ? <Check />
                        : <X />}
                    </span>
                  </>
                ) : (
                  <div className="live-turn__content">
                    <span className="live-turn__role">
                      {item.role === "caller"
                        ? "You"
                        : "Assistant"}
                    </span>

                    <p dir="auto">
                      {item.text}

                      {item.partial
                        && depth === 0
                        && (
                          <span
                            className="live-turn__caret"
                            aria-hidden="true"
                          />
                        )}
                    </p>
                  </div>
                )}
              </motion.article>
            );
          })}
        </AnimatePresence>

        {items.length === 0
          && session.isConnected
          && (
            <motion.div
              className="live-conversation__waiting"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <LoaderCircle aria-hidden="true" />
              Listening for the first turn
            </motion.div>
          )}
      </div>
    </aside>
  );
}
