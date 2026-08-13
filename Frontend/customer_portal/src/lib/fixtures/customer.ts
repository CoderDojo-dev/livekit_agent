/**
 * lib/fixtures/customer.ts - sample data for surfaces with no endpoint yet.
 * The `customer` record moved to /api/v1/me/profile/detail (see lib/api/me.server.ts).
 * Aucun nom, montant ou date invente ailleurs.
 */
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
  {
    id: "sec_02",
    label: "Password changed",
    detail: "London, United Kingdom",
    at: "12 March, 18:02",
  },
  { id: "sec_03", label: "Signed in", detail: "Manchester, United Kingdom", at: "6 March, 11:47" },
  { id: "sec_04", label: "New device added", detail: "iPhone 15", at: "28 February, 20:31" },
  {
    id: "sec_05",
    label: "Signed out of all devices",
    detail: "London, United Kingdom",
    at: "14 February, 08:05",
  },
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
