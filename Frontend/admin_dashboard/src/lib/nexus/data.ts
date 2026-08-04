// Part IV reference data. Literal, character for character. Nothing invented.

/* ---------------- SECONDARY SCREENS ---------------- */

export const RULES = [
  {
    name: "Route billing intents to Finance",
    trigger: "Intent = billing",
    action: "Assign team Finance",
    runs: "1,204",
    status: "enabled",
  },
  {
    name: "Escalate after two failed answers",
    trigger: "AI confidence < 0.4",
    action: "Escalate to advisor",
    runs: "318",
    status: "enabled",
  },
  {
    name: "Auto-close silent tickets",
    trigger: "No reply for 7 days",
    action: "Set status closed",
    runs: "96",
    status: "disabled",
  },
];
