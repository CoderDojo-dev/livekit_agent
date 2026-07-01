import { useEffect, useState } from "react";
import { api } from "../api";
import type { Escalation } from "../types";

export function EscalationQueue({ onInspect }: { onInspect: (sessionId: string) => void }) {
  const [rows, setRows] = useState<Escalation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.escalations("open").then((r) => setRows(r.escalations)).catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">Could not load escalations: {error}</p>;
  if (!rows) return <p className="muted">Loading escalations…</p>;
  if (rows.length === 0) return <p className="muted">No open escalations.</p>;

  return (
    <table className="grid">
      <thead>
        <tr>
          <th>Trigger</th>
          <th>Target</th>
          <th>Session</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((e) => (
          <tr key={e.id}>
            <td><span className="tag">{e.trigger}</span></td>
            <td>{e.target}</td>
            <td className="mono">{e.session_id.slice(0, 8)}…</td>
            <td>
              <button onClick={() => onInspect(e.session_id)}>Inspect</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}