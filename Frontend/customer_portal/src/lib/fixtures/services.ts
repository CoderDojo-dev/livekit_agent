export const plan = {
  name: "Standard",
  price: "£24.00",
  period: "per month",
  renews: "1 April",
  description: "Voice support, call handling, and a shared line for one team.",
  included: [
    "Unlimited assistant conversations",
    "Callbacks with a specialist",
    "Two call-handling blocks each month",
    "12-month transcript history",
  ],
} as const;

export const usage = [
  { id: "usg_1", label: "Call-handling blocks", used: 4, limit: 2, unit: "blocks" },
  { id: "usg_2", label: "Specialist callbacks", used: 1, limit: 4, unit: "callbacks" },
  { id: "usg_3", label: "Transcript storage", used: 62, limit: 100, unit: "%" },
] as const;

export const addons = [
  {
    id: "add_1",
    name: "Call recording",
    price: "£4.00",
    period: "per month",
    since: "8 March",
    description: "Keeps an audio-free written record of every specialist call.",
    active: true,
  },
  {
    id: "add_2",
    name: "Priority routing",
    price: "£9.00",
    period: "per month",
    since: "2 January",
    description: "Your requests are placed ahead of the standard queue.",
    active: true,
  },
] as const;

export const available = [
  {
    id: "avl_1",
    name: "Extra call-handling block",
    price: "£6.00",
    period: "per month",
    description: "Adds one more block of handled calls to your monthly allowance.",
  },
  {
    id: "avl_2",
    name: "Weekend cover",
    price: "£12.00",
    period: "per month",
    description: "Specialists available on Saturday and Sunday, 09:00 to 18:00.",
  },
  {
    id: "avl_3",
    name: "Second line",
    price: "£18.00",
    period: "per month",
    description: "A separate number with its own routing rules.",
  },
] as const;
