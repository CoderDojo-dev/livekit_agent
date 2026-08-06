import { Modal } from "@/components/nexus/modal";
import { Token } from "@/components/nexus/primitives";
import { AGENT_LANGUAGES, DOMAIN_CATALOG, INSTRUCTION_LAYERS } from "@/lib/nexus/agent-catalog";
import { formatInteger } from "@/lib/nexus/format";
import { formatLastSeen, sharePercent, type AgentRow } from "@/lib/nexus/agent-view";

export function AgentDetail({ row, onClose }: { row: AgentRow; onClose: () => void }) {
  const entry = row.catalog;
  const owned = entry?.owns ? DOMAIN_CATALOG.find((domain) => domain.key === entry.owns) : null;
  const routed = entry ? DOMAIN_CATALOG.filter((domain) => entry.routes.includes(domain.key)) : [];

  return (
    <Modal open title={row.label} onClose={onClose}>
      <div className="grid gap-sp-7">
        <section>
          <p className="t-caption text-ink-4">{row.className}</p>
          <p className="t-ui mt-sp-4 text-ink-2">
            {entry?.role ??
              "This persona was observed in call turns but is not present in the transcribed catalog. The catalog is likely stale against the deployed agent worker."}
          </p>
          {entry ? <p className="t-caption mt-sp-4 text-ink-4">Source: {entry.source}</p> : null}
        </section>

        <section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-label text-ink-3">Observed activity</p>
          <div className="mt-sp-5 grid grid-cols-3 gap-sp-5">
            <div>
              <p className="t-mono-l text-ink-1">{formatInteger(row.turns)}</p>
              <p className="t-caption text-ink-4">Caller turns</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">{sharePercent(row.turnShare)}</p>
              <p className="t-caption text-ink-4">Share of turns</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">{formatLastSeen(row.lastSeen)}</p>
              <p className="t-caption text-ink-4">Last seen</p>
            </div>
          </div>
        </section>

        {entry ? (
          <section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
            <p className="t-label text-ink-3">Position in the persona graph</p>
            <div className="mt-sp-5 flex flex-wrap gap-sp-4">
              {entry.entryPoint ? (
                <Token mono={false} strong>
                  Starts every call
                </Token>
              ) : null}
              {entry.terminal ? (
                <Token mono={false} strong>
                  Final escalation point
                </Token>
              ) : null}
              {owned ? <Token mono={false}>Owns {owned.key}</Token> : null}
              {routed.map((domain) => (
                <Token key={domain.key} mono={false}>
                  Routes {domain.key}
                </Token>
              ))}
            </div>
            {entry.terminal ? (
              <p className="t-caption mt-sp-5 text-ink-4">
                Derived, not configured: this persona has no escalate_to_manager tool, which is what
                makes it terminal.
              </p>
            ) : null}
          </section>
        ) : null}

        {owned ? (
          <section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
            <p className="t-label text-ink-3">Spoken transition line</p>
            <p className="t-caption mt-sp-4 text-ink-4">What the caller hears when routed here.</p>
            <div className="mt-sp-5 grid gap-sp-4">
              {AGENT_LANGUAGES.map((code) => (
                <div key={code} className="flex items-start gap-sp-5">
                  <Token>{code}</Token>
                  <span className="t-ui text-ink-2" dir={code === "ar" ? "rtl" : "ltr"}>
                    {owned.lines[code]}
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-label text-ink-3">Instruction layers</p>
          <p className="t-caption mt-sp-4 text-ink-4">
            Assembled at construction from the persona's registered tools. Read-only: personas are
            code, not configuration.
          </p>
          <div className="mt-sp-5">
            {INSTRUCTION_LAYERS.map((layer) => (
              <div
                key={layer.name}
                className="border-b border-stroke-subtle py-sp-5 last:border-b-0"
              >
                <span className="t-ui text-ink-1">{layer.name}</span>
                {layer.conditional ? (
                  <span className="t-label ml-auto text-ink-3">{layer.conditional}</span>
                ) : null}
                <p className="t-caption mt-sp-4 text-ink-4">{layer.detail}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </Modal>
  );
}
