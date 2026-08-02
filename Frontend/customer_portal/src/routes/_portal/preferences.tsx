import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { copy } from "@/lib/copy";
import {
  Button,
  Card,
  Divider,
  Segmented,
  SectionLabel,
  SwitchRow,
} from "@/components/portal/primitives";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_portal/preferences")({
  head: () => ({
    meta: [
      { title: "Preferences — Nexus Customer Portal" },
      {
        name: "description",
        content:
          "Choose the assistant voice, speaking pace, confirmation behaviour, notifications, and how long transcripts are kept.",
      },
      { property: "og:title", content: "Preferences — Nexus Customer Portal" },
      {
        property: "og:description",
        content: "How the assistant behaves and how the portal looks.",
      },
    ],
  }),
  component: PreferencesScreen,
});

const SECTIONS = [
  { id: "assistant", label: copy.preferences.nav.assistant },
  { id: "voice", label: copy.preferences.nav.voice },
  { id: "appearance", label: copy.preferences.nav.appearance },
  { id: "notifications", label: copy.preferences.nav.notifications },
  { id: "history", label: copy.preferences.nav.history },
] as const;

function PreferencesScreen() {
  const [section, setSection] = useState<(typeof SECTIONS)[number]["id"]>("assistant");
  const [confirm, setConfirm] = useState(true);
  const [remember, setRemember] = useState(true);
  const [proactive, setProactive] = useState(false);
  const [pushToTalk, setPushToTalk] = useState(false);
  const [captions, setCaptions] = useState(true);
  const [noise, setNoise] = useState(true);
  const [echo, setEcho] = useState(true);
  const [reduceMotion, setReduceMotion] = useState(false);
  const [voice, setVoice] = useState("Neutral");
  const [pace, setPace] = useState(2);
  const [length, setLength] = useState<string>(copy.preferences.lengths[1]!);
  const [density, setDensity] = useState<string>(copy.preferences.densities[0]!);
  const [textSize, setTextSize] = useState<string>(copy.preferences.textSizes[0]!);
  const [retention, setRetention] = useState<string>(copy.preferences.retentions[2]!);
  const [confirmDialog, setConfirmDialog] = useState(false);

  return (
    <div className="grid gap-sp-8 lg:grid-cols-[220px_minmax(0,1fr)]">
      <nav className="lg:sticky lg:top-24 lg:self-start">
        <ul className="space-y-sp-1">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => setSection(s.id)}
                className={cn(
                  "focus-ring t-ui flex h-9 w-full items-center rounded-r-2 px-sp-5 text-left transition-colors duration-200",
                  section === s.id
                    ? "bg-surface-3 text-ink-1"
                    : "text-ink-4 hover:bg-surface-2 hover:text-ink-2",
                )}
              >
                {s.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <div className="space-y-sp-8">
        {section === "assistant" && (
          <Card>
            <SectionLabel>{copy.preferences.assistant}</SectionLabel>
            <div className="mt-sp-4 divide-y divide-stroke-subtle">
              <SwitchRow
                {...copy.preferences.switches.confirm}
                checked={confirm}
                onChange={(v) => (v ? setConfirm(true) : setConfirmDialog(true))}
              />
              <SwitchRow
                {...copy.preferences.switches.remember}
                checked={remember}
                onChange={setRemember}
              />
              <SwitchRow
                {...copy.preferences.switches.proactive}
                checked={proactive}
                onChange={setProactive}
              />
            </div>
            <Divider className="my-sp-7" />
            <div className="t-label text-ink-4">{copy.preferences.responseLength}</div>
            <div className="mt-sp-4">
              <Segmented
                label={copy.preferences.responseLength}
                options={copy.preferences.lengths}
                value={length}
                onChange={setLength}
              />
            </div>
          </Card>
        )}

        {section === "voice" && (
          <Card>
            <SectionLabel>{copy.preferences.voice}</SectionLabel>
            <div className="t-label mt-sp-7 text-ink-4">{copy.preferences.assistantVoice}</div>
            <div className="mt-sp-4 grid gap-sp-5 sm:grid-cols-2">
              {copy.preferences.voices.map((v) => (
                <button
                  key={v.name}
                  onClick={() => setVoice(v.name)}
                  aria-pressed={voice === v.name}
                  className={cn(
                    "focus-ring rounded-r-3 border p-sp-6 text-left transition-colors duration-200",
                    voice === v.name
                      ? "border-stroke-ink bg-surface-3"
                      : "border-stroke-subtle bg-surface-2 hover:border-stroke-default",
                  )}
                >
                  <div className="t-body-strong text-ink-1">{v.name}</div>
                  <div className="t-caption mt-sp-1 text-ink-4">{v.description}</div>
                </button>
              ))}
            </div>

            <Divider className="my-sp-7" />

            <div className="t-label text-ink-4">{copy.preferences.speakingPace}</div>
            <input
              type="range"
              min={0}
              max={4}
              step={1}
              value={pace}
              aria-label={copy.preferences.speakingPace}
              onChange={(e) => setPace(Number(e.target.value))}
              className="mt-sp-5 w-full accent-white"
            />
            <div className="t-micro-2 mt-sp-3 flex justify-between text-ink-5">
              <span>{copy.preferences.paceLabels[0]}</span>
              <span>{copy.preferences.paceLabels[2]}</span>
              <span>{copy.preferences.paceLabels[4]}</span>
            </div>

            <Divider className="my-sp-7" />

            <div className="divide-y divide-stroke-subtle">
              <SwitchRow
                {...copy.preferences.switches.pushToTalk}
                checked={pushToTalk}
                onChange={setPushToTalk}
              />
              <SwitchRow
                {...copy.preferences.switches.captions}
                checked={captions}
                onChange={setCaptions}
              />
              <SwitchRow
                {...copy.preferences.switches.noise}
                checked={noise}
                onChange={setNoise}
              />
              <SwitchRow
                {...copy.preferences.switches.echo}
                checked={echo}
                onChange={setEcho}
              />
            </div>
          </Card>
        )}

        {section === "appearance" && (
          <Card>
            <SectionLabel>{copy.preferences.appearance}</SectionLabel>
            <div className="mt-sp-7 space-y-sp-7">
              <div>
                <div className="t-label text-ink-4">{copy.preferences.density}</div>
                <div className="mt-sp-4">
                  <Segmented
                    label={copy.preferences.density}
                    options={copy.preferences.densities}
                    value={density}
                    onChange={setDensity}
                  />
                </div>
              </div>
              <div>
                <div className="t-label text-ink-4">{copy.preferences.textSize}</div>
                <div className="mt-sp-4">
                  <Segmented
                    label={copy.preferences.textSize}
                    options={copy.preferences.textSizes}
                    value={textSize}
                    onChange={setTextSize}
                  />
                </div>
              </div>
              <Divider />
              <SwitchRow
                {...copy.preferences.switches.reduceMotion}
                checked={reduceMotion}
                onChange={setReduceMotion}
              />
            </div>
          </Card>
        )}

        {section === "notifications" && (
          <Card>
            <SectionLabel>{copy.preferences.notifications}</SectionLabel>
            <table className="mt-sp-7 w-full">
              <thead>
                <tr>
                  <th className="t-micro-2 pb-sp-5 text-left text-ink-5">EVENT</th>
                  {copy.preferences.channels.map((c) => (
                    <th key={c} className="t-micro-2 pb-sp-5 text-center text-ink-5">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {copy.preferences.events.map((e, ri) => (
                  <tr key={e} className="border-t border-stroke-subtle">
                    <td className="t-ui py-sp-5 pr-sp-6 text-ink-2">{e}</td>
                    {copy.preferences.channels.map((c, ci) => (
                      <td key={c} className="py-sp-5 text-center">
                        <NotificationToggle initial={(ri + ci) % 3 !== 2} label={`${e} — ${c}`} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {section === "history" && (
          <Card>
            <SectionLabel>{copy.preferences.history}</SectionLabel>
            <div className="t-label mt-sp-7 text-ink-4">{copy.preferences.retention}</div>
            <div className="mt-sp-4">
              <Segmented
                label={copy.preferences.retention}
                options={copy.preferences.retentions}
                value={retention}
                onChange={setRetention}
              />
            </div>
          </Card>
        )}
      </div>

      {/* 43.6 — la confirmation avant de retirer les confirmations */}
      {confirmDialog && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-n-0/70 p-sp-8">
          <div className="w-full max-w-md rounded-r-5 border border-stroke-strong bg-surface-2 p-sp-8 shadow-elev-4">
            <h2 className="t-title-2 text-ink-1">{copy.preferences.confirmDialog.title}</h2>
            <p className="t-body mt-sp-4 text-ink-3">{copy.preferences.confirmDialog.body}</p>
            <p className="t-caption mt-sp-4 text-ink-5">
              {copy.preferences.confirmDialog.detail}
            </p>
            <div className="mt-sp-8 flex justify-end gap-sp-4">
              <Button variant="secondary" onClick={() => setConfirmDialog(false)}>
                {copy.preferences.confirmDialog.keep}
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setConfirm(false);
                  setConfirmDialog(false);
                }}
              >
                {copy.preferences.confirmDialog.turnOff}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function NotificationToggle({ initial, label }: { initial: boolean; label: string }) {
  const [on, setOn] = useState(initial);
  return (
    <button
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => setOn((v) => !v)}
      className={cn(
        "focus-ring h-5 w-5 rounded-r-1 border transition-colors duration-200",
        on ? "border-transparent bg-n-12" : "border-stroke-strong bg-surface-3",
      )}
    />
  );
}
