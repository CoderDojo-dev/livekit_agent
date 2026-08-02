/**
 * lib/fixtures/customer.ts — donnees d'exemple canoniques, chapitre 54.
 * Aucun nom, montant ou date invente ailleurs.
 */
export const customer = {
  id: "cus_8f21a9",
  fullName: "Amara Osei",
  preferredName: "Amara",
  initials: "AO",
  email: "amara.osei@fieldnote.co",
  phone: "+44 7700 900142",
  dateOfBirth: "1988-03-14",
  reference: "NX-4471-0293",
  customerSince: "2021-06-02",
  language: "English (United Kingdom)",
  region: "United Kingdom",
  timeZone: "Europe/London (GMT+1)",
  dateFormat: "14 March 1988",
  numberFormat: "1,234.56",
  billingAddress: ["48 Bramley Road", "Flat 3", "London", "W10 6SP", "United Kingdom"],
  serviceAddressSame: true,
  planName: "Standard",
  planPrice: "£24.00",
  planPeriod: "per month",
} as const;

export const sessions = [
  {
    id: "ses_01",
    device: "MacBook Pro",
    browser: "Safari 18",
    location: "London, United Kingdom",
    lastActive: "Active now",
    current: true,
  },
  {
    id: "ses_02",
    device: "iPhone 15",
    browser: "Nexus app",
    location: "London, United Kingdom",
    lastActive: "2 hours ago",
    current: false,
  },
  {
    id: "ses_03",
    device: "Windows PC",
    browser: "Chrome 131",
    location: "Manchester, United Kingdom",
    lastActive: "6 days ago",
    current: false,
  },
] as const;

export const securityEvents = [
  { id: "sec_01", label: "Signed in", detail: "London, United Kingdom", at: "Today, 09:14" },
  { id: "sec_02", label: "Password changed", detail: "London, United Kingdom", at: "12 March, 18:02" },
  { id: "sec_03", label: "Signed in", detail: "Manchester, United Kingdom", at: "6 March, 11:47" },
  { id: "sec_04", label: "New device added", detail: "iPhone 15", at: "28 February, 20:31" },
  { id: "sec_05", label: "Signed out of all devices", detail: "London, United Kingdom", at: "14 February, 08:05" },
] as const;

export const notifications = [
  {
    id: "ntf_01",
    title: "Your March invoice is ready",
    detail: "£24.00 due on 1 April",
    at: "2 hours ago",
    unread: true,
  },
  {
    id: "ntf_02",
    title: "Request REQ-2043 was updated",
    detail: "A specialist added a note.",
    at: "Yesterday",
    unread: true,
  },
  {
    id: "ntf_03",
    title: "Callback scheduled",
    detail: "Thursday at 14:30",
    at: "3 days ago",
    unread: false,
  },
] as const;
