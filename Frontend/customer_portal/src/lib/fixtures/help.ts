export const topics = [
  { id: "top_1", name: "Getting started", count: 8, icon: "compass" },
  { id: "top_2", name: "Talking to the assistant", count: 12, icon: "audio-lines" },
  { id: "top_3", name: "Billing and invoices", count: 9, icon: "receipt-text" },
  { id: "top_4", name: "Plans and add-ons", count: 6, icon: "layers-2" },
  { id: "top_5", name: "Privacy and data", count: 7, icon: "shield" },
  { id: "top_6", name: "Accessibility", count: 4, icon: "accessibility" },
] as const;

export const popular = [
  {
    id: "art_1",
    title: "How the assistant confirms changes before making them",
    topic: "Talking to the assistant",
    minutes: 3,
  },
  {
    id: "art_2",
    title: "Reading your invoice line by line",
    topic: "Billing and invoices",
    minutes: 4,
  },
  {
    id: "art_3",
    title: "What happens to your transcripts",
    topic: "Privacy and data",
    minutes: 2,
  },
  {
    id: "art_4",
    title: "Asking for a specialist callback",
    topic: "Getting started",
    minutes: 2,
  },
  {
    id: "art_5",
    title: "Using the portal with a screen reader",
    topic: "Accessibility",
    minutes: 5,
  },
] as const;
