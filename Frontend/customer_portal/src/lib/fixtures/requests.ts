export type RequestStatus = "open" | "in_progress" | "resolved" | "closed";

export type RequestEvent = {
  id: string;
  label: string;
  body: string | null;
  at: string;
  author: "you" | "assistant" | "specialist";
};

export type CustomerRequest = {
  id: string;
  ref: string;
  title: string;
  summary: string;
  status: RequestStatus;
  opened: string;
  updated: string;
  needsYou: boolean;
  events: readonly RequestEvent[];
};

export const requests: readonly CustomerRequest[] = [
  {
    id: "req_2043",
    ref: "REQ-2043",
    title: "Crackling on outbound calls",
    summary:
      "Outbound calls from the Manchester line have intermittent crackling after the first minute.",
    status: "in_progress",
    opened: "17 March",
    updated: "Yesterday, 16:52",
    needsYou: true,
    events: [
      {
        id: "ev_1",
        label: "Request received",
        body: "Opened during a conversation with the assistant.",
        at: "17 March, 16:40",
        author: "assistant",
      },
      {
        id: "ev_2",
        label: "Picked up by a specialist",
        body: null,
        at: "17 March, 17:15",
        author: "specialist",
      },
      {
        id: "ev_3",
        label: "Specialist added a note",
        body: "We ran a line test and saw packet loss between 17:02 and 17:09. Could you tell us whether the crackling happens on calls under one minute?",
        at: "Yesterday, 16:52",
        author: "specialist",
      },
    ],
  },
  {
    id: "req_2038",
    ref: "REQ-2038",
    title: "Invoice address on PDF is out of date",
    summary: "The February PDF still shows the old flat number.",
    status: "open",
    opened: "14 March",
    updated: "14 March, 09:20",
    needsYou: false,
    events: [
      {
        id: "ev_1",
        label: "Request received",
        body: "Opened from the Billing screen.",
        at: "14 March, 09:20",
        author: "you",
      },
    ],
  },
  {
    id: "req_2017",
    ref: "REQ-2017",
    title: "Add a second contact to the account",
    summary: "Requested that a colleague be able to call in about service issues.",
    status: "resolved",
    opened: "2 March",
    updated: "5 March, 11:04",
    needsYou: false,
    events: [
      { id: "ev_1", label: "Request received", body: null, at: "2 March, 10:11", author: "you" },
      {
        id: "ev_2",
        label: "Picked up by a specialist",
        body: null,
        at: "2 March, 13:40",
        author: "specialist",
      },
      {
        id: "ev_3",
        label: "Resolved",
        body: "A second contact was added and can now verify by phone.",
        at: "5 March, 11:04",
        author: "specialist",
      },
    ],
  },
  {
    id: "req_1994",
    ref: "REQ-1994",
    title: "Explain the January proration",
    summary: "Asked why January was £6.00 lower than the usual monthly amount.",
    status: "closed",
    opened: "18 February",
    updated: "19 February, 08:30",
    needsYou: false,
    events: [
      {
        id: "ev_1",
        label: "Request received",
        body: null,
        at: "18 February, 15:02",
        author: "you",
      },
      {
        id: "ev_2",
        label: "Closed",
        body: "The assistant explained the mid-month change and you confirmed no further help was needed.",
        at: "19 February, 08:30",
        author: "assistant",
      },
    ],
  },
] as const;
