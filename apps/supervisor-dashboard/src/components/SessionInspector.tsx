import { useEffect, useState } from "react";
import { api } from "../api";
import type { SessionDetail, Verdict } from "../types";

function verdictClass(verdict: string): string {
  if (verdict === "REFUSED") return "verdict refused";
  if (verdict === "ESCALATE") return "verdict escalate";
  return "verdict authorized";
}

export function SessionInspector({ initialId }: { initialId: string }) {
  const [id, setId] = useState(initialId);
  const [query, setQuery] = useState(initialId);
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [verdicts, setVerdicts] = useState<Verdict[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setId(initialId), [initialId]);

  useEffect(() => {
    if (!id) return;
    setError(null);
    setSession(null);
    setVerdicts(null);
    api.session(id).then(setSession).catch((e) => setError(String(e)));
    api.verdicts(id).then((r) => setVerdicts(r.verdicts)).catch(() => setVerdicts([]));
  }, [id]);

  return (
    <div>
      <div className="searchbar">
        <input
          value={query}
          placeholder="session id (UUID)"
          onChange={(e) => setQuery(e.target.value)}
        />
        <button onClick={() => setId(query.trim())}>Open</button>
      </div>

      {error && <p className="error">{error}</p>}
      {!id && <p className="muted">Enter a session id, or pick one from the escalation queue.</p>}

      {session && (
        <>
          <div className="session-meta">
            <span>Disposition: <b>{session.disposition ?? "—"}</b></span>
            <span>Duration: <b>{session.duration_seconds ?? "—"}s</b></span>
            <span>Peak frustration: <b>{session.max_frustration.toFixed(2)}</b></span>
          </div>

          <h3>Why the system decided as it did</h3>
          {verdicts && verdicts.length > 0 ? (
            <ul className="verdicts">
              {verdicts.map((v) => (
                <li key={v.id} className={verdictClass(v.verdict)}>
                  <div className="verdict-head">
                    <span className="badge">{v.verdict}</span>
                    <span className="mono">{v.action}</span>
                    <span className="rule">{v.rule_id}</span>
                  </div>
                  <div className="justification">{v.justification}</div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No policy verdicts recorded for this session.</p>
          )}

          <h3>Transcript (PII-masked)</h3>
          <div className="transcript">
            {session.turns.map((t) => (
              <div className={`turn ${t.speaker}`} key={`${t.index}-${t.speaker}`}>
                <span className="who">{t.speaker === "caller" ? "Caller" : t.agent ?? "Agent"}</span>
                <span className="text">{t.text}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}