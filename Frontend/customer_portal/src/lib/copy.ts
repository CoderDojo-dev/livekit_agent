/**
 * lib/copy.ts — chapitre 55. Aucune chaine visible n'est ecrite dans un composant.
 */

/** The one place the product name lives. Every wordmark, document title and
 *  metadata entry derives from this object — a rebrand is a one-line change. */
export const brand = {
  name: "Client Portal",
  /** Suffix for document titles. Every route head must derive from this. */
  titleSuffix: "Client Portal",
  tagline: "Voice support that respects your time.",
  version: "Version 1.0.0",
} as const;

/** Build a document title. Use this in every route head — never a literal. */
export const pageTitle = (section?: string) =>
  section ? `${section} - ${brand.titleSuffix}` : brand.titleSuffix;

export const copy = {
  brand: {
    name: brand.name,
    tagline: brand.tagline,
    version: brand.version,
  },
  shell: {
    search: "Search",
    notifications: "Notifications",
    notificationsEmpty: "Nothing new.",
    account: "Account",
    signOut: "Sign out",
    language: "Language",
    collapseRail: "Collapse navigation",
    expandRail: "Expand navigation",
    secure: "SECURE",
    // Labels name the destination, not the current state: the button is a
    // switch, so "Switch to light" is what a screen reader should announce.
    theme: { light: "Switch to light theme", dark: "Switch to dark theme" },
    menu: { profile: "Your profile", security: "Security" },
  },
  login: {
    title: brand.name,
    subtitle: "Sign in to your self-service portal.",
    submit: "Sign in",
    pending: "Signing in…",
    newHere: "New here? Create your secure sign-in.",
    notice: {
      manual: "You are signed out.",
      expired: "Your session expired. Sign in again.",
      password: "Your password was changed. Sign in with the new one.",
      revoked: "All devices were signed out. Sign in again.",
    },
  },
  signup: {
    title: "Create your sign-in",
    subtitle: "A password keeps your data out of other people's hands.",
    passwordLabel: "Password (at least 10 characters)",
    confirmLabel: "Confirm password",
    cinLabel: "Last 4 digits of your CIN",
    phoneLabel: "Phone number on the account",
    mismatch: "Those two passwords are not the same.",
    submit: "Create my sign-in",
    pending: "Creating your sign-in…",
    haveOne: "Already have a sign-in? Use it here.",
  },
  assistant: {
    title: "Private voice support, whenever you need it.",
    start: "Start conversation",
    end: "End",
    connecting: "Connecting…",
    enableAudio: "Enable assistant audio",
    assurance: {
      encrypted: "Encrypted end to end",
      audioOnly: "Audio only",
      noRecording: "Never recorded",
    },
    /*
     * The ambient prompts that drift across the scene while no call is running.
     *
     * They exist to answer the question the empty screen actually provokes —
     * "what am I allowed to say?" — before the customer has to ask it. Every
     * one of them is something the assistant can genuinely do: the list is a
     * subset of copy.about.can, never a wish list. The `id` is the icon key in
     * the backdrop; nothing here is read aloud, because a rotating aria-live
     * region is hostile, and copy.assistant.state already says the same thing
     * to a screen reader once.
     */
    prompts: [
      { id: "ask", label: "Ask a question" },
      { id: "problem", label: "Report a problem" },
      { id: "bill", label: "Explain my bill" },
      { id: "balance", label: "Check my balance" },
      { id: "request", label: "Track a request" },
      { id: "callback", label: "Arrange a call back" },
      { id: "person", label: "Speak to a person" },
      { id: "plan", label: "Change my plan" },
    ],
    state: {
      disconnected: {
        label: "Ready when you are",
        detail: "Start a private conversation with the assistant.",
      },
      connecting: {
        label: "Opening a secure line",
        detail: "This usually takes a moment.",
      },
      preConnect: {
        label: "Getting your microphone ready",
        detail: "You can start speaking now.",
      },
      initializing: { label: "The assistant is joining", detail: "Almost there." },
      idle: { label: "Ready to listen", detail: "Speak whenever you are ready." },
      listening: { label: "Listening", detail: "Go ahead." },
      thinking: { label: "Working on it", detail: "Checking your account." },
      speaking: { label: "Speaking", detail: "You can interrupt at any time." },
      failed: {
        label: "Connection needs attention",
        detail: "End the conversation and try again.",
      },
    },
    stream: {
      heading: "LIVE CONVERSATION",
      assistant: "ASSISTANT",
      you: "YOU",
      willAppear: "Your conversation will appear here as you speak.",
      waiting: "Listening for the first words…",
      captionsOff: "Captions are off. Turn them on in Preferences to read along.",
    },
    controls: {
      mute: "Mute microphone",
      unmute: "Unmute microphone",
    },
    tools: {
      heading: "SERVICE ACTION",
      working: "Checking this for you…",
      done: "Completed",
      failed: "Did not complete",
      genericDone: "Checked something for you",
      genericFailed: "Could not finish that just now",
      nowWith: (persona: string) => `Now with ${persona}`,
    },
    summary: {
      heading: "CONVERSATION SUMMARY",
      duration: "DURATION",
      turns: "TURNS",
      ended: "Conversation ended.",
      turnsPending: "Saving…",
      savedNote: "A written record of this conversation appears in your activity shortly.",
      resume: "Resume",
    },
    errors: {
      generic: "We could not open the line. Try again in a moment.",
      microphone: "We need access to your microphone to start a conversation.",
      timeout: "The assistant did not join in time. Try again.",
    },
  },
  personas: {
    // Keys are conversation.turns.active_agent values produced by the worker
    // (type(self).__name__ on each agent class, verified in apps/agent-worker).
    // Unknown keys fall back — a raw identifier must never reach the screen.
    fallback: "Assistant",
    TriageAgent: "Assistant",
    BillingAgent: "Billing support",
    TechnicalAgent: "Technical support",
    ManagerAgent: "Specialist",
    AccountServicesAgent: "Account support",
  },
  activity: {
    heroLabel: "LAST CONVERSATION",
    when: "When",
    open: "Open conversation",
    tabs: {
      all: "All",
      conversations: "Conversations",
      requests: "Requests",
      callbacks: "Callbacks",
      secondary: {
        calls: "Calls",
        messages: "Messages",
      },
    },
    search: "Search activity",
    duration: "duration",
    turns: "turns",
    transcript: "TRANSCRIPT",
    callbackTime: "CALLBACK TIME",
    callbackWindow: "PREFERRED WINDOW",
    requestReference: "REFERENCE",
    requestCreated: "CREATED",
    requestUpdated: "UPDATED",
    requestPriority: "PRIORITY",
    requestCategory: "CATEGORY",
    cadence: {
      label: "CADENCE",
      /* Two modes, because the data has two shapes. Saying "over time" when the
         turns carried no timestamps would be a small lie on a small chart. */
      overTime: "Turn cadence over the conversation",
      inSequence: "Turn order (no timing recorded)",
      agent: "assistant",
      caller: "you",
      split: (agent: number, caller: number) => `${agent} assistant · ${caller} you`,
      describe: (turns: number, agent: number, caller: number) =>
        `${turns} turns: ${agent} from the assistant, ${caller} from you.`,
    },
  },
  requests: {
    heroLabel: "NEEDS YOUR ATTENTION",
    open: "Open request",
    tabs: { active: "Active", resolved: "Resolved", all: "All" },
    search: "Search requests",
    reference: "REFERENCE",
    created: "CREATED",
    updated: "UPDATED",
    priority: "PRIORITY",
    category: "CATEGORY",
    timeline: "TIMELINE",
    empty: {
      title: "No requests here",
      body: "No requests open. If something is wrong, ask the assistant and it can raise one for you.",
      action: "Show all requests",
    },
  },
  services: {
    plan: "YOUR PLAN",
    balances: "BALANCES",
    overAllowance: "You are over your monthly allowance.",
    renews: (date: string) => `Renews on ${date}`,
    activeSince: (date: string) => `Active since ${date}`,
    tiles: {
      credit: "Credit",
      lines: "Active lines",
      linesHint: (total: number) => `of ${total} total`,
      plan: "Plan",
    },
    expires: (on: string) => `expires ${on}`,
    recharges: "Top-ups",
    /** Chip beside a balance whose allowance runs out inside the week. */
    expiringSoon: "Expiring soon",
    balancesEmpty: {
      title: "No balances yet",
      body: "Balances appear here once your line is active. If you expect credit, ask the assistant to check the line.",
    },
    rechargesEmpty: {
      title: "No top-ups yet",
      body: "Top-ups you make by app, web, USSD, scratch card or at an agent appear here with any bonus credit.",
    },
    subscriptionsEmpty: {
      title: "No lines on this account",
      body: "If you have a line that is missing here, open a request and we will connect it to your account.",
    },
  },
  billing: {
    amountDue: "AMOUNT DUE",
    invoices: "INVOICES",
    bonus: (n: string) => `Plus ${n} bonus`,
    total: "TOTAL",
    issued: "ISSUED",
    due: "DUE",
    /* The three tiles that qualify the amount due. Every one of them is a
       figure the /me/billing payload already carried and the screen threw
       away - a card with one number on it and a third of the page empty under
       it was a layout problem caused by unused data, not by spacing. */
    invoiceCount: "INVOICES",
    invoiceCountHint: (paid: number) => `${paid} settled`,
    lastPayment: "LAST PAYMENT",
    nextDue: "NEXT DUE",
    nextDueNone: "Nothing scheduled",
    noPaymentYet: "None yet",
    settled: "Settled",
    outstandingOf: (paid: string, total: string) => `${paid} of ${total} settled`,
    payments: "PAYMENTS",
    paymentsNote: "The most recent payments we have recorded against your account.",
    noPayments: {
      title: "No payments recorded",
      body: "Payments settled against your invoices appear here with the method used.",
    },
    noInvoices: {
      title: "No invoices yet",
      body: "Postpaid invoices appear here after your first billing cycle.",
    },
    prepaidPointer: "Your prepaid credit, bundles and top-ups live in Services.",
    prepaidPointerAction: "Open Services",
  },
  help: {
    browse: "BROWSE BY TOPIC",
    stillStuck: "STILL NEED HELP?",
    contactBody:
      "The assistant can answer most questions instantly, and hand you to a specialist when it cannot.",
    talkToAssistant: "Talk to the assistant",
    openRequest: "Open a request",
    faqHeading: "COMMON QUESTIONS",
    faqIntro: "The six things people ask before they call for the first time.",
    /*
     * Every answer below restates something the product already guarantees
     * elsewhere - about.dataBody, about.can, about.cannot,
     * preferences.agentLanguageNote, profile.locked. Nothing here is a new
     * promise, because a help page that invents behaviour is worse than a help
     * page that is missing.
     */
    faq: [
      {
        q: "Am I speaking to a real person?",
        a: "No. The assistant is automated. It says so at the start of every conversation, and it can pass you to a human specialist the moment you ask or the moment it cannot help.",
      },
      {
        q: "Is my voice recorded?",
        a: "No audio is ever stored. Your words are turned into text so the assistant can understand them, and a masked written record is kept so you and our advisors can refer back to it.",
      },
      {
        q: "Can it actually change things on my account?",
        a: "For a defined set of actions, yes — and it tells you what it is about to do before it does it. You can stop it at any point. It can never take a payment or change your password.",
      },
      {
        q: "What language will it speak?",
        a: "French, Arabic or English. Set the language new conversations open in under Preferences, and ask the assistant to switch at any point during a call — asking always wins.",
      },
      {
        q: "What if it gets something wrong?",
        a: "Ask it to pass you to a person, or open a request from this page. Everything the assistant did during your conversation is listed in Activity, so an advisor can see exactly what happened.",
      },
      {
        q: "Why can I not edit my details here?",
        a: "Your name, reference and addresses come from your account record and are read-only in the portal, so nothing can be changed by someone who reaches an unlocked screen. Ask the assistant if anything is wrong.",
      },
    ],
    quickHeading: "IN A HURRY?",
    topics: {
      plan: {
        title: "Plans and subscriptions",
        body: "See your current plan, switch options, and view add-ons.",
        action: "See your balances →",
      },
      bill: {
        title: "Invoices and payments",
        body: "View past invoices, download statements, and update payment details.",
        action: "View your invoices →",
      },
      request: {
        title: "Raise and track requests",
        body: "Check the status of any request you've raised or the assistant raised for you.",
        action: "See your tickets →",
      },
      security: {
        title: "Account security",
        body: "Manage sessions, passwords, and sign-in history.",
        action: "Check sessions →",
      },
      assistant: {
        title: "Use the assistant",
        body: "Start a voice call, check past conversations, and understand what the assistant can do.",
        action: "Start a call →",
      },
    },
  },
  profile: {
    navLabel: "Profile sections",
    /** Copies the customer reference to the clipboard. */
    copied: "Copied to your clipboard.",
    copyFailed: "Your browser would not let us copy that.",
    nav: {
      identity: "Identity",
      contact: "Contact",
      addresses: "Addresses",
      locale: "Language and region",
    },
    identity: "IDENTITY",
    contact: "CONTACT",
    addresses: "ADDRESSES",
    locale: "LANGUAGE AND REGION",
    changePhoto: "Change photo",
    remove: "Remove",
    edit: "Edit",
    copy: "Copy",
    locked: "This cannot be changed here. Ask the assistant if it is wrong.",
    reveal: "Reveal",
    hide: "Hide",
    billingAddress: "Billing address",
    serviceAddress: "Service address",
    sameAddress: "Service address is the same as billing address",
    unsaved: (n: number) => `${n} unsaved change${n === 1 ? "" : "s"}`,
    discard: "Discard",
    save: "Save changes",
    saved: "Profile updated",
    customerSince: (date: string) => `Customer since ${date}`,
    sessionsMoved: "Manage where you are signed in ->",
    fields: {
      fullName: "Full name",
      preferredName: "Preferred name",
      dateOfBirth: "Date of birth",
      reference: "Customer reference",
      email: "Email",
      phone: "Phone",
      language: "Portal display language",
      scopeNote:
        "These settings apply to this browser only. The language your assistant speaks follows your account and is set when you speak to us.",
      region: "Region",
      timeZone: "Time zone",
      dateFormat: "Date format",
      numberFormat: "Number format",
    },
  },
  preferences: {
    /** Names the section switcher for assistive technology. */
    navLabel: "Preference sections",
    nav: {
      appearance: "Appearance",
      voice: "Voice and audio",
      language: "Language",
    },
    appearance: "APPEARANCE",
    voice: "VOICE AND AUDIO",
    language: "LANGUAGE",
    theme: "Theme",
    themes: ["Dark", "Light"],
    density: "Density",
    densities: ["Comfortable", "Compact"],
    textSize: "Text size",
    textSizes: ["Default", "Large"],
    agentLanguage: "Preferred agent language",
    agentLanguageHint: "The language a new conversation opens in.",
    /*
     * The precedence is agent-worker's, not the portal's
     * (config/language_policy.resolve_session_language). Stating it here is the
     * difference between a setting the customer trusts and one they think is
     * broken the first time they ask the assistant to switch mid-call.
     */
    agentLanguageNote:
      "Asking the assistant to switch during a conversation always wins. Without a saved preference, conversations open in French.",
    agentLanguageOptions: {
      fr: "Français",
      ar: "العربية",
      en: "English",
    },
    agentLanguageSaving: "Saving…",
    agentLanguageSaved: (language: string) => `New conversations will open in ${language}.`,
    agentLanguageUnchanged: "Already your preferred language.",
    switches: {
      captions: {
        label: "Show captions by default",
        description: "Captions appear under the assistant while it speaks.",
      },
      reduceMotion: {
        label: "Reduce motion",
        description: "Slows the assistant visual and removes non-essential animation.",
      },
    },
    reduceMotionNote:
      "Applies across the portal immediately, including the assistant visual. Your system setting still wins when it asks for reduced motion.",
  },
  security: {
    navLabel: "Security sections",
    nav: {
      signIn: "Sign-in",
      sessions: "Active sessions",
      activity: "Recent activity",
    },
    signIn: "SIGN-IN",
    sessions: "ACTIVE SESSIONS",
    activity: "RECENT ACTIVITY",
    password: "Password",
    changePassword: "Change password",
    currentPassword: "Current password",
    newPassword: "New password",
    passwordRule: "At least 10 characters. Changing it signs you out everywhere.",
    savePassword: "Change password",
    savingPassword: "Changing…",
    passwordChangedSignOut: "Password changed. Signing you out…",
    revokedSignOut: "Signing out every device…",
    revokedCount: (n: number) => `${n} session${n === 1 ? "" : "s"} signed out.`,
    lastChanged: (when: string) => `Last changed ${when}`,
    lastChangedNever: "Never changed",
    thisDevice: "This device",
    signOutAll: "Sign out of every device",
    signedIn: "Signed in",
    sessionsEmpty: "Only this device is signed in.",
  },
  about: {
    tagline: "Voice support that respects your time.",
    howHeading: "HOW THE ASSISTANT WORKS",
    canHeading: "WHAT IT CAN DO",
    cannotHeading: "WHAT IT CANNOT DO",
    dataHeading: "YOUR DATA",
    dataBody:
      "Your voice is never stored as audio. A masked, written record of each conversation is kept so you and our advisors can refer back to it. Nothing you say is used to train anyone else's assistant.",
    how: [
      {
        n: "01",
        t: "You speak",
        b: "Your voice is streamed over an encrypted connection. Nothing is recorded as audio.",
      },
      {
        n: "02",
        t: "It listens",
        b: "Your words are turned into text so the assistant can understand what you need.",
      },
      {
        n: "03",
        t: "It acts",
        b: "When it needs information from your account, it asks the system directly and shows you what it did.",
      },
      {
        n: "04",
        t: "You confirm",
        b: "Before anything changes, it tells you what it is about to do. You can stop it at any time.",
      },
    ],
    can: [
      "Look up your account",
      "Update your details",
      "Explain your invoices",
      "Open and track requests",
      "Schedule a callback",
      "Hand you to a specialist",
    ],
    cannot: [
      "Make payments on your behalf",
      "Access other customers' data",
      "Change your password",
      "Speak to anyone but you",
      "Record video or your screen",
      "Keep listening after you end a call",
    ],
    footer: ["Terms", "Privacy", "Accessibility"],
  },
  empty: {
    activityA: {
      title: "No activity yet",
      body: "No calls yet. Start one from the Assistant tab and it will appear here.",
      action: "Start your first conversation",
    },
    callbacks: {
      title: "No callbacks scheduled",
      body: "The assistant can arrange one at a time that suits you.",
    },
    notifications: {
      title: "No messages from us recently",
      body: "Alerts about your line appear here.",
    },
    filtered: {
      title: "Nothing matches",
      body: "Try a different search or clear the filters.",
      action: "Clear filters",
    },
    generic: "Nothing here yet.",
  },
  common: {
    back: "Back",
    tryAgain: "Try again",
    close: "Close",
    loading: "Loading",
    notApplicable: "\u2014",
    couldNotLoad: "We could not load this",
    pagination: "Pages",
    previous: "Previous page",
    next: "Next page",
    pageOf: (page: number, pages: number, total: number) =>
      `Page ${page} of ${pages} · ${total} item${total === 1 ? "" : "s"}`,
    shareOf: (value: number, of: number) => `${value} of ${of}`,
  },
  labels: {
    // conversation.call_sessions.final_disposition
    disposition: {
      resolved: "Resolved",
      escalated: "Passed to a specialist",
      dropped: "Disconnected",
      abandoned: "Ended early",
    },
    channel: { voice: "Voice", whatsapp: "WhatsApp", web: "Web", chat: "Chat" },
    // ticketing.tickets.status — five values (copy.requests.status had four)
    requestStatus: {
      open: "Received",
      in_progress: "In progress",
      pending: "Waiting on us",
      resolved: "Resolved",
      closed: "Closed",
    },
    requestCategory: {
      network_complaint: "Network",
      formal_complaint: "Formal complaint",
      technical: "Technical",
      billing: "Billing",
      other: "Other",
    },
    priority: { low: "Low", medium: "Medium", high: "High", urgent: "Urgent" },
    invoiceStatus: {
      draft: "Draft",
      issued: "Issued",
      paid: "Paid",
      partial: "Partly paid",
      overdue: "Overdue",
      disputed: "Disputed",
      void: "Cancelled",
    },
    balanceType: { main: "Credit", data: "Data", voice: "Calls", sms: "Texts" },
    rechargeChannel: {
      app: "App",
      web: "Web",
      ussd: "USSD",
      scratch_card: "Scratch card",
      agent: "In store",
    },
    /* billing.recharges.status. The rows rendered the raw enum - "completed",
       lowercase, straight from the OCS - next to five labels that had all been
       translated. Truth in labelling is not optional on one column. */
    rechargeStatus: { pending: "Pending", completed: "Completed", failed: "Failed" },
    /* billing.payments.method and .status. Both columns are constrained enums
       in packages/persistence (method IN card|bank_transfer|wallet|voucher|cash,
       status IN pending|succeeded|failed|refunded) and both reach the portal as
       plain strings, so each map falls back to the raw value rather than
       rendering nothing for a value added later. */
    paymentMethod: {
      card: "Card",
      bank_transfer: "Bank transfer",
      wallet: "Wallet",
      voucher: "Voucher",
      cash: "Cash",
    },
    paymentStatus: {
      pending: "Pending",
      succeeded: "Paid",
      failed: "Failed",
      refunded: "Refunded",
    },
    notificationChannel: { sms: "Text message", whatsapp: "WhatsApp", email: "Email" },
    notificationStatus: { queued: "Queued", sent: "Sent", failed: "Not delivered" },
    callbackStatus: { pending: "Scheduled", completed: "Done", cancelled: "Cancelled" },
    speaker: { caller: "You", agent: "Assistant" },
  },
  notificationTemplates: {
    // Extend as templates appear; unknown codes fall back to genericMessage.
    invoice_ready: "Your invoice is ready",
    payment_received: "We received your payment",
    payment_failed: "A payment did not go through",
    plan_changed: "Your plan was changed",
    ticket_update: "An update on one of your requests",
    callback_scheduled: "We scheduled a call back",
  },
  notifications: {
    heading: "RECENT MESSAGES",
    /** Footer of the topbar tray. The tray holds twenty; Activity holds all. */
    seeAll: "See every message",
    genericMessage: "A message about your account",
    empty: "No messages from us recently. Alerts about your line appear here.",
  },
  errors: {
    notFoundTitle: "We could not find that page",
    notFoundBody: "The page may have moved, or the link may be out of date.",
    brokenTitle: "This page did not load",
    brokenBody: "Something went wrong on our side. Try again, or go back to the start.",
    goHome: "Go to the assistant",
    signedOut: "You have been signed out.",
    sessionExpired: "Your session has expired. Sign in again.",
  },
} as const;

/**
 * conversation.turns.active_agent -> customer wording.
 * Render rule: copy.personas[turn.agent ?? ""] ?? copy.personas.fallback.
 * A raw identifier such as billing_agent_v2 must never reach the screen.
 */
export function personaLabel(agent: string | null | undefined): string {
  return (copy.personas as Record<string, string>)[agent ?? ""] ?? copy.personas.fallback;
}
