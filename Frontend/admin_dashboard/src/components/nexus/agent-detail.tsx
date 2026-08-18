import { Modal } from "@/components/nexus/modal";
import { Td, Th, Token } from "@/components/nexus/primitives";
import {
  AgentActivitySparkline,
  type AgentSparklineMetric,
} from "@/components/nexus/agent-activity-sparkline";
import { AGENT_LANGUAGES, DOMAIN_CATALOG, INSTRUCTION_LAYERS } from "@/lib/nexus/agent-catalog";
import { formatInteger } from "@/lib/nexus/format";
import {
  formatDuration,
  formatLastSeen,
  sharePercent,
  type AgentRow,
} from "@/lib/nexus/agent-view";

export function AgentDetail({
  row,
  metric,
  onClose,
}: {
  row: AgentRow;
  metric: AgentSparklineMetric;
  onClose: () => void;
}) {
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
          <p className="t-caption mt-sp-4 text-ink-4">
            Duration is the complete persisted call duration attributed non-exclusively to this AI
            persona. Calls involving multiple personas contribute duration to each persona.
          </p>
          <div className="mt-sp-5 grid grid-cols-2 gap-sp-5 md:grid-cols-4">
            <div>
              <p className="t-mono-l text-ink-1">{formatInteger(row.attributedCalls)}</p>
              <p className="t-caption text-ink-4">Attributed calls</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">{sharePercent(row.attributionShare)}</p>
              <p className="t-caption text-ink-4">Share of persona-call attributions</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">{formatInteger(row.completedCalls)}</p>
              <p className="t-caption text-ink-4">Completed calls</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">
                {formatDuration(row.attributedCallDurationSeconds)}
              </p>
              <p className="t-caption text-ink-4">Attributed call duration</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">
                {row.averageCompletedCallDurationSeconds === null
                  ? "\u2014"
                  : formatDuration(row.averageCompletedCallDurationSeconds)}
              </p>
              <p className="t-caption text-ink-4">Average completed-call duration</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">
                {row.providerInputTokens === null
                  ? "Unavailable"
                  : formatInteger(row.providerInputTokens)}
              </p>
              <p className="t-caption text-ink-4">Input tokens</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">
                {row.providerOutputTokens === null
                  ? "Unavailable"
                  : formatInteger(row.providerOutputTokens)}
              </p>
              <p className="t-caption text-ink-4">Output tokens</p>
            </div>
            <div>
              <p className="t-mono-l text-ink-1">{formatLastSeen(row.lastObservedAt)}</p>
              <p className="t-caption text-ink-4">Last observed</p>
            </div>
          </div>
        </section>

        <section className="mt-sp-6 border-t border-stroke-subtle pt-sp-5">
          <p className="t-label text-ink-3">Daily trend</p>
          <div className="mt-sp-5">
            <AgentActivitySparkline
              points={row.daily}
              metric={metric}
              label={`${row.label} ${
                metric === "duration" ? "attributed call duration" : "provider token"
              } trend over ${row.daily.length} days`}
            />
          </div>
          <div className="mt-sp-6 overflow-hidden rounded-r-4 border border-stroke-default">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <Th>Day</Th>
                  <Th align="right">Attributed calls</Th>
                  <Th align="right">Duration</Th>
                  <Th align="right">Input tokens</Th>
                  <Th align="right">Output tokens</Th>
                </tr>
              </thead>
              <tbody>
                {row.daily.map((point) => (
                  <tr key={point.day} className="border-b border-stroke-subtle last:border-b-0">
                    <Td>
                      <span className="t-mono text-ink-2">{point.day}</span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {formatInteger(point.attributed_calls)}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {formatDuration(point.attributed_call_duration_seconds)}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {point.provider_input_tokens === null
                          ? "Unavailable"
                          : formatInteger(point.provider_input_tokens)}
                      </span>
                    </Td>
                    <Td align="right">
                      <span className="t-mono text-ink-3">
                        {point.provider_output_tokens === null
                          ? "Unavailable"
                          : formatInteger(point.provider_output_tokens)}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </table>
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
