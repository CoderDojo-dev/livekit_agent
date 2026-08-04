import { Token } from "@/components/nexus/primitives";
import { sentimentByIndex, sentimentTone, turnKey } from "@/lib/nexus/call-view";
import type { SentimentRow, TranscriptTurnRow } from "@/lib/api/sessions.server";
import { cn } from "@/lib/utils";

export function Transcript({
  turns,
  sentiment,
}: {
  turns: TranscriptTurnRow[];
  sentiment: SentimentRow[];
}) {
  const byIndex = sentimentByIndex(sentiment);

  return (
    <ul>
      {turns.map((turn) => {
        const isCaller = turn.speaker === "caller";
        // F5 — sentiment measures the CALLER. Never paint the agent's line with it.
        const mood = isCaller ? byIndex.get(turn.index) : undefined;

        return (
          <li key={turnKey(turn)} className="border-t border-stroke-subtle px-sp-7 py-sp-6">
            <div className="flex flex-wrap items-center gap-sp-4">
              <span className="t-mono-s text-ink-5">#{turn.index}</span>
              <span className="t-micro text-ink-4">{isCaller ? "Caller" : "Agent"}</span>
              {turn.agent ? <Token mono={false}>{turn.agent}</Token> : null}
              {mood ? (
                <span className="flex items-center gap-sp-3">
                  <span
                    aria-hidden="true"
                    className={cn("block size-[6px] rounded-[1px]", sentimentTone(mood.label))}
                  />
                  <span className="t-caption text-ink-4">
                    {mood.label}
                    {"\u00b7 " + mood.score.toFixed(1)}
                  </span>
                </span>
              ) : null}
            </div>
            {/* F4 — transcript_masked is ALREADY PII-masked. Do not scrub it again. */}
            <p className={cn("t-body mt-sp-3", isCaller ? "text-ink-2" : "text-ink-3")}>
              {turn.text?.trim() || <span className="text-ink-5">(no transcript captured)</span>}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
