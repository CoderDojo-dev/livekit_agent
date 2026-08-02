export type InvoiceStatus = "paid" | "pending" | "failed" | "refunded" | "void";

export type Invoice = {
  id: string;
  ref: string;
  period: string;
  date: string;
  amount: string;
  status: InvoiceStatus;
};

export const nextCharge = {
  amount: "£34.00",
  date: "1 April",
  method: "Visa ending 4417",
  lines: [
    { label: "Standard plan", amount: "£24.00" },
    { label: "Call recording", amount: "£4.00" },
    { label: "Priority routing", amount: "£9.00" },
    { label: "Credit applied", amount: "-£3.00" },
  ],
} as const;

export const paymentMethod = {
  brand: "Visa",
  last4: "4417",
  expiry: "09 / 27",
  holder: "A OSEI",
} as const;

export const spend = [
  { month: "OCT", value: 24 },
  { month: "NOV", value: 24 },
  { month: "DEC", value: 30 },
  { month: "JAN", value: 18 },
  { month: "FEB", value: 24 },
  { month: "MAR", value: 36 },
] as const;

export const invoices: readonly Invoice[] = [
  { id: "inv_0312", ref: "NX-0312", period: "March", date: "1 March", amount: "£36.00", status: "pending" },
  { id: "inv_0298", ref: "NX-0298", period: "February", date: "1 February", amount: "£24.00", status: "paid" },
  { id: "inv_0284", ref: "NX-0284", period: "January", date: "1 January", amount: "£18.00", status: "paid" },
  { id: "inv_0271", ref: "NX-0271", period: "December", date: "1 December", amount: "£30.00", status: "paid" },
  { id: "inv_0259", ref: "NX-0259", period: "November", date: "1 November", amount: "£24.00", status: "failed" },
  { id: "inv_0246", ref: "NX-0246", period: "October", date: "1 October", amount: "£24.00", status: "paid" },
  { id: "inv_0233", ref: "NX-0233", period: "September", date: "1 September", amount: "£24.00", status: "refunded" },
] as const;
