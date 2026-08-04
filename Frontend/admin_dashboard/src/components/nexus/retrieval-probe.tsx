import { useState } from "react";
import { Button, Card, CardHeader, TextField } from "@/components/nexus/primitives";
import { InlineError } from "@/components/nexus/states";
import { probeSearch } from "@/lib/api/knowledge.server";
import { formatScore } from "@/lib/nexus/knowledge-view";
import type { Passage } from "@/lib/api/knowledge.server";

/**
 * F16 — the retrieval probe asks what the agent would actually retrieve. It is the only way to
 * catch a "stray upload outranking real procedures". POST but non-mutating; not cached (no query
 * key) and never invalidates the inventory. F16 also forbids language/document_type/min_score
 * filters and any score colour-coding.
 */
export function RetrievalProbe() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<Passage[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);

  async function run() {
    if (!query.trim() || pending) return;
    setError(null);
    setResult(null);
    setPending(true);
    try {
      const data = await probeSearch({ data: { query: query.trim() } });
      setResult(data.passages);
    } catch (e) {
      // F10 — a 503 here means the index is unusable; never render as an empty result list.
      setError(e);
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Retrieval probe"
        subtitle="Runs the same query path the agent uses — what would it retrieve for this question?"
      />
      <div className="mt-sp-6 flex items-start gap-sp-4">
        <TextField
          label="Query"
          placeholder="e.g. How many days of roaming are included?"
          className="max-w-[420px]"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void run();
          }}
        />
        <Button variant="primary" disabled={pending || !query.trim()} onClick={() => void run()}>
          {pending ? "Searching\u2026" : "Probe"}
        </Button>
      </div>

      {error ? (
        <div className="mt-sp-6">
          <InlineError error={error} />
        </div>
      ) : null}

      {result?.length === 0 ? (
        <p className="t-caption mt-sp-6 text-ink-4">No passages retrieved.</p>
      ) : null}

      {result && result.length > 0 ? (
        <ol className="mt-sp-6 flex flex-col gap-sp-6">
          {result.map((passage) => (
            <li key={`${passage.source}:${passage.version}`} className="flex gap-sp-5">
              <span className="t-mono w-[2ch] shrink-0 text-ink-4">
                {result.indexOf(passage) + 1}
              </span>
              {/* F16 — raw score, no confidence colouring (E5 scores cluster ~0.7-1.0). */}
              <span className="t-mono shrink-0 text-ink-3">{formatScore(passage.score)}</span>
              <div className="min-w-0">
                <p className="t-mono truncate text-ink-2">{passage.source}</p>
                <p className="t-ui mt-sp-1 line-clamp-3 text-ink-2">{passage.text}</p>
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </Card>
  );
}
