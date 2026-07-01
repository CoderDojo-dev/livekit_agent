import { useState } from "react";
import { EscalationQueue } from "./components/EscalationQueue";
import { KpiPanel } from "./components/KpiPanel";
import { SessionInspector } from "./components/SessionInspector";

type Tab = "kpis" | "escalations" | "session";

export default function App() {
  const [tab, setTab] = useState<Tab>("kpis");
  const [sessionId, setSessionId] = useState("");

  const inspect = (id: string) => {
    setSessionId(id);
    setTab("session");
  };

  return (
    <div className="app">
      <header>
        <h1>Supervisor Dashboard</h1>
        <nav>
          <button className={tab === "kpis" ? "active" : ""} onClick={() => setTab("kpis")}>KPIs</button>
          <button className={tab === "escalations" ? "active" : ""} onClick={() => setTab("escalations")}>
            Escalations
          </button>
          <button className={tab === "session" ? "active" : ""} onClick={() => setTab("session")}>
            Session inspector
          </button>
        </nav>
      </header>

      <main>
        {tab === "kpis" && <KpiPanel />}
        {tab === "escalations" && <EscalationQueue onInspect={inspect} />}
        {tab === "session" && <SessionInspector initialId={sessionId} />}
      </main>
    </div>
  );
}