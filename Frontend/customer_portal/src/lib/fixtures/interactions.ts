export type InteractionKind = "conversation" | "request" | "callback";

export type Interaction = {
  id: string;
  kind: InteractionKind;
  title: string;
  summary: string;
  at: string;
  relative: string;
  duration: string | null;
  turns: number | null;
  actions: number;
  changed: readonly string[];
  transcript: readonly { speaker: "assistant" | "you" | "specialist"; text: string; at: string }[];
};

export const interactions: readonly Interaction[] = [
  {
    id: "int_2291",
    kind: "conversation",
    title: "Explained the March invoice",
    summary:
      "You asked why March was higher than February. The assistant walked through the two extra call-handling blocks and confirmed nothing was charged twice.",
    at: "Today, 09:12",
    relative: "2 hours ago",
    duration: "4m 18s",
    turns: 14,
    actions: 2,
    changed: [],
    transcript: [
      { speaker: "you", text: "Why is March higher than February?", at: "00:04" },
      {
        speaker: "assistant",
        text: "March includes two extra call-handling blocks that were added on 8 March. Each block is £6.00, so the total is £12.00 above your usual amount.",
        at: "00:09",
      },
      { speaker: "you", text: "Was anything charged twice?", at: "00:31" },
      {
        speaker: "assistant",
        text: "No. I checked every line on the invoice and each charge appears once.",
        at: "00:35",
      },
    ],
  },
  {
    id: "int_2288",
    kind: "request",
    title: "Opened a request about call quality",
    summary:
      "Reported crackling on outbound calls from the Manchester line. A specialist picked it up the same afternoon.",
    at: "Yesterday, 16:40",
    relative: "Yesterday",
    duration: null,
    turns: null,
    actions: 1,
    changed: ["Request REQ-2043 created"],
    transcript: [],
  },
  {
    id: "int_2284",
    kind: "conversation",
    title: "Updated your phone number",
    summary:
      "You replaced the old mobile number with +44 7700 900142 and confirmed the change out loud before it was saved.",
    at: "12 March, 18:02",
    relative: "6 days ago",
    duration: "2m 05s",
    turns: 8,
    actions: 1,
    changed: ["Phone changed to +44 7700 900142"],
    transcript: [
      { speaker: "you", text: "I need to change my phone number.", at: "00:03" },
      {
        speaker: "assistant",
        text: "Of course. What is the new number?",
        at: "00:06",
      },
      { speaker: "you", text: "Plus four four, seven seven zero zero, nine zero zero one four two.", at: "00:11" },
      {
        speaker: "assistant",
        text: "I have +44 7700 900142. Shall I save it as your main number?",
        at: "00:19",
      },
      { speaker: "you", text: "Yes please.", at: "00:24" },
      { speaker: "assistant", text: "Saved. Your phone number is now +44 7700 900142.", at: "00:27" },
    ],
  },
  {
    id: "int_2279",
    kind: "callback",
    title: "Callback with a billing specialist",
    summary:
      "Scheduled for Thursday at 14:30 to review the annual plan options before renewal.",
    at: "9 March, 11:20",
    relative: "9 days ago",
    duration: null,
    turns: null,
    actions: 1,
    changed: ["Callback scheduled for Thursday 14:30"],
    transcript: [],
  },
  {
    id: "int_2270",
    kind: "conversation",
    title: "Added the call recording add-on",
    summary:
      "You asked what recording would cost. The assistant explained the £4.00 monthly charge and added it after you confirmed.",
    at: "8 March, 10:03",
    relative: "10 days ago",
    duration: "3m 41s",
    turns: 11,
    actions: 2,
    changed: ["Call recording add-on activated"],
    transcript: [
      { speaker: "you", text: "How much is call recording?", at: "00:02" },
      {
        speaker: "assistant",
        text: "Call recording is £4.00 per month on your Standard plan. It applies from the next billing date.",
        at: "00:06",
      },
      { speaker: "you", text: "Add it.", at: "00:18" },
      {
        speaker: "assistant",
        text: "I am about to add call recording at £4.00 per month. Shall I go ahead?",
        at: "00:21",
      },
      { speaker: "you", text: "Yes.", at: "00:26" },
      { speaker: "assistant", text: "Added. It is active from 1 April.", at: "00:29" },
    ],
  },
  {
    id: "int_2261",
    kind: "conversation",
    title: "Checked the renewal date",
    summary: "Confirmed the Standard plan renews on 1 April and that the price is unchanged.",
    at: "2 March, 08:47",
    relative: "16 days ago",
    duration: "1m 12s",
    turns: 5,
    actions: 1,
    changed: [],
    transcript: [
      { speaker: "you", text: "When does my plan renew?", at: "00:02" },
      {
        speaker: "assistant",
        text: "Your Standard plan renews on 1 April at £24.00. The price has not changed.",
        at: "00:05",
      },
    ],
  },
] as const;
