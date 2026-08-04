/**
 * Static persona catalog, transcribed from the agent-worker source at
 * version_79 (eda5f58). There is no endpoint for this data: personas are
 * Python classes, not rows (Cookbook 12 §0.1).
 *
 * `className` MUST match `type(self).__name__`, which is what
 * conversation.turns.active_agent stores (base_agent.py).
 *
 * If a persona is added or renamed in apps/agent-worker/src/agents/, this file
 * goes stale. Drift is surfaced at runtime, not hidden: any class name observed
 * in the database but missing here renders as an "Unrecognized persona" row.
 */

export type AgentDomainKey = "billing" | "account" | "technical";

export type AgentCatalogEntry = {
  className: string;
  label: string;
  role: string;
  /** Domain owned by this persona, or null for Triage/Manager. */
  owns: AgentDomainKey | null;
  /** Domains this persona can route away. */
  routes: AgentDomainKey[];
  /** True when escalate_to_manager is absent -> derived terminal point. */
  terminal: boolean;
  /** True when this persona starts every call (server.py). */
  entryPoint: boolean;
  source: string;
};

export const AGENT_CATALOG: AgentCatalogEntry[] = [
  {
    className: "TriageAgent",
    label: "Triage",
    role: "Entry persona. Starts every call and routes to a specialist.",
    owns: null,
    routes: ["billing", "account", "technical"],
    terminal: false,
    entryPoint: true,
    source: "agents/triage_agent.py",
  },
  {
    className: "BillingAgent",
    label: "Billing",
    role: "Balance, invoice, payment and deferral requests.",
    owns: "billing",
    routes: [],
    terminal: false,
    entryPoint: false,
    source: "agents/billing_agent.py",
  },
  {
    className: "AccountServicesAgent",
    label: "Account Services",
    role: "Plan, recharge, roaming and phone-line requests.",
    owns: "account",
    routes: [],
    terminal: false,
    entryPoint: false,
    source: "agents/account_services_agent.py",
  },
  {
    className: "TechnicalAgent",
    label: "Technical",
    role: "SIM, network and connectivity problems.",
    owns: "technical",
    routes: [],
    terminal: false,
    entryPoint: false,
    source: "agents/technical_agent.py",
  },
  {
    className: "ManagerAgent",
    label: "Manager",
    role: "Final escalation point. Claims no domain; uses transfer_to_human.",
    owns: null,
    routes: [],
    terminal: true,
    entryPoint: false,
    source: "agents/manager_agent.py",
  },
];

/** Transcribed verbatim from agents/domains.py (DOMAINS). */
export type DomainCatalogEntry = {
  key: AgentDomainKey;
  ownTopics: string;
  routeTool: string;
  lines: { fr: string; ar: string; en: string };
};

export const DOMAIN_CATALOG: DomainCatalogEntry[] = [
  {
    key: "billing",
    ownTopics: "Balance, invoice, payment and deferral requests",
    routeTool: "route_to_billing",
    lines: {
      fr: "Très bien, je vous mets en relation avec notre service de facturation.",
      ar: "حسنًا، سأحوّلك إلى قسم الفوترة لدينا.",
      en: "Sure, I'm connecting you with our billing department.",
    },
  },
  {
    key: "account",
    ownTopics: "Plan, recharge, roaming and phone-line requests",
    routeTool: "route_to_account_services",
    lines: {
      fr: "Très bien, je vous mets en relation avec notre service de gestion de compte.",
      ar: "حسنًا، سأحوّلك إلى قسم إدارة الحساب لدينا.",
      en: "Sure, I'm connecting you with our account services team.",
    },
  },
  {
    key: "technical",
    ownTopics: "SIM, network and connectivity problems",
    routeTool: "route_to_technical",
    lines: {
      fr: "Très bien, je vous mets en relation avec notre service technique.",
      ar: "حسنًا، سأحوّلك إلى الدعم الفني لدينا.",
      en: "Sure, I'm connecting you with our technical support.",
    },
  },
];

/** Shared instruction layers every persona receives (instruction_kit.py). */
export const INSTRUCTION_LAYERS = [
  {
    name: "Persona core",
    detail: "Hand-written domain prose, unique to each persona.",
    conditional: null as string | null,
  },
  {
    name: "Knowledge abstention rule",
    detail:
      "Ground answers strictly in retrieved passages; speak them, never read them aloud verbatim.",
    conditional: "only when knowledge_search is available",
  },
  {
    name: "Routing mandate",
    detail:
      "Projected from the registered tool set. A persona that cannot route a domain away is told it owns it.",
    conditional: null,
  },
  {
    name: "Closing protocol",
    detail:
      "Confirm nothing else is needed, then call end_conversation; the tool delivers the farewell.",
    conditional: null,
  },
  {
    name: "Language switch policy",
    detail: "Never drift; switch only on an explicit caller request via switch_spoken_language.",
    conditional: null,
  },
  {
    name: "TTS language lock",
    detail: "Speak only the configured language.",
    conditional: "only when a TTS provider is configured",
  },
];

export const AGENT_LANGUAGES = ["fr", "ar", "en"] as const;
