/**
 * lib/format.ts — one formatter for the whole portal.
 *
 * Currency is TND (billing.accounts.currency_code defaults to 'TND') and the
 * operational timezone is Africa/Tunis (CALLBACK_TIMEZONE in the backend).
 * Locale is en-GB so dates read 16 August 2026, matching the existing copy deck.
 */
const LOCALE = "en-GB";
export const TIME_ZONE = "Africa/Tunis";

export const DEFAULT_CURRENCY = "TND";

/**
 * ISO 4217 alphabetic codes are exactly three letters. Intl.NumberFormat with
 * style:"currency" throws RangeError on anything else, and a thrown RangeError
 * inside render reaches the router's errorComponent - the customer then sees
 * "This page did not load" instead of a billing page.
 *
 * me_reads.billing() legitimately returns currency_code "" for a customer with
 * no billing accounts (every prepaid-only customer). That is an honest "no
 * account, so no currency", not a malformed response, so the formatter absorbs
 * it and falls back to the operational currency rather than the page dying.
 */
function currencyOrDefault(currency: string | null | undefined): string {
  if (typeof currency !== "string") return DEFAULT_CURRENCY;
  const code = currency.trim().toUpperCase();
  return /^[A-Z]{3}$/.test(code) ? code : DEFAULT_CURRENCY;
}

export function money(
  value: number | null | undefined,
  currency: string | null | undefined = DEFAULT_CURRENCY,
): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: currencyOrDefault(currency),
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 3, // TND is a 3-decimal currency (millimes)
  }).format(value);
}

export function quantity(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined) return "—";
  if (unit === "TND") return money(value);
  const formatted = new Intl.NumberFormat(LOCALE, {
    maximumFractionDigits: unit === "GB" ? 2 : 0,
  }).format(value);
  return `${formatted} ${unit}`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

/** "3 minutes ago", "2 days ago" — last-active and last-changed rows. */
export function relative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const deltaSeconds = Math.round((then - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  const steps: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31536000],
    ["month", 2592000],
    ["week", 604800],
    ["day", 86400],
    ["hour", 3600],
    ["minute", 60],
  ];
  for (const [unit, seconds] of steps) {
    if (Math.abs(deltaSeconds) >= seconds) {
      return rtf.format(Math.round(deltaSeconds / seconds), unit);
    }
  }
  return rtf.format(deltaSeconds, "second");
}

/** duration_seconds -> "4m 18s". Replaces the hardcoded value on /assistant. */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  return minutes > 0 ? `${minutes}m ${String(rest).padStart(2, "0")}s` : `${rest}s`;
}

/**
 * Device line for /security, derived from user_agent (max 200 chars in the DB).
 * Deliberately coarse: no UA parsing library, no fingerprinting, and an unknown
 * agent is labelled honestly rather than guessed at.
 */
export function deviceLabel(userAgent: string | null): string {
  if (!userAgent) return "Unknown device";
  const ua = userAgent.toLowerCase();
  const os = ua.includes("iphone")
    ? "iPhone"
    : ua.includes("ipad")
      ? "iPad"
      : ua.includes("android")
        ? "Android"
        : ua.includes("mac os")
          ? "Mac"
          : ua.includes("windows")
            ? "Windows"
            : ua.includes("linux")
              ? "Linux"
              : "Unknown device";
  const browser = ua.includes("edg/")
    ? "Edge"
    : ua.includes("chrome/") && !ua.includes("chromium")
      ? "Chrome"
      : ua.includes("firefox/")
        ? "Firefox"
        : ua.includes("safari/")
          ? "Safari"
          : "Browser";
  return `${browser} on ${os}`;
}
