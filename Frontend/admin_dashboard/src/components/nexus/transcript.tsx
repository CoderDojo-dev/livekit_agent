import { Token } from "@/components/nexus/primitives";
import { sentimentByIndex, sentimentTone, turnKey } from "@/lib/nexus/call-view";
import type { SentimentRow, TranscriptTurnRow } from "@/lib/api/sessions.server";
import { cn } from "@/lib/utils";

/**
 * A conversation, in a fixed-height reading window.
 *
 * It previously rendered every turn inline, so a 60-turn call produced a page several thousand
 * pixels tall and the verdicts panel below it was effectively unreachable. The transcript is the
 * one place on this page where scrolling is the RIGHT answer — you read a conversation in order
 * and scroll back for what was said earlier — but that scrolling has to be contained.
 *
 * `overscroll-contain` stops a wheel that reaches the end of the transcript from continuing into
 * the page behind it, which is the behaviour that made the old nested scrollers feel broken.
 */
export function Transcript({
  turns,
  sentiment,
}: {
  turns: TranscriptTurnRow[];
  sentiment: SentimentRow[];
}) {
  const byIndex = sentimentByIndex(sentiment);

  return (
    <ul
      /* Sized in viewport units so the panel always ends inside the window, on a laptop and on a
       * 27" display alike, instead of being pinned to one hard-coded pixel height. */
      className="max-h-[min(52vh,560px)] overflow-y-auto overscroll-contain"
      tabIndex={0}
      role="log"
      aria-label="Call transcript"
    >
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
