// Chapter 9 — every value in the product is formatted here, nowhere else.
const LOCALE = "en-US";

export function formatInteger(value: number): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(value);
}

export function formatCompact(value: number): string {
  return new Intl.NumberFormat(LOCALE, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatPercent(value: number, digits = 1): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** 12.4 -> "+12.4%" ; -1.8 -> "\u22121.8%" (typographic minus U+2212) */
export function formatDelta(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "\u2212" : "";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

export function formatCurrency(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const value = bytes / Math.pow(1024, i);
  const digits = i === 0 ? 0 : value < 10 ? 1 : 0;
  return `${value.toFixed(digits)} ${units[i]}`;
}

/** 252 -> "04:12" */
export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]!.toUpperCase())
    .join("");
}

/*
 * Phone rendering.
 *
 * The previous `maskPhone` was broken for the format this platform actually stores. Given
 * "+21626078277" (no spaces), `phone.indexOf(" ")` returns -1, so `indexOf(" ", -1 + 1)` is also
 * -1, and `slice(0, -1)` drops a single trailing character instead of falling back to the
 * intended 3-character head. The rendered result was the entire number, then dots, then a repeat
 * of its own last four digits.
 *
 * It is replaced rather than repaired. Chapter 31.6 asked for masking, but this is an operator
 * console: /callbacks exists so an advisor can RING THE PERSON BACK, and a masked number cannot
 * be dialled. Transcripts remain PII-masked at capture on the backend - that protection is
 * untouched, and is a different concern from the CRM contact field.
 *
 * To restore masking, change the return of `formatPhone`; every call site already routes here.
 */

/** Country codes this platform serves. Longest-first so "216" wins before "21" or "1". */
const COUNTRY_CODES = [
  "966",
  "971",
  "216",
  "213",
  "212",
  "218",
  "44",
  "49",
  "39",
  "34",
  "33",
  "20",
  "1",
];

/**
 * Groups subscriber digits in threes from the right: 26078277 -> "26 078 277".
 *
 * Two refinements over a naive chunker:
 *  - a 10-digit subscriber is grouped 3-3-4, the convention every NANP reader expects;
 *  - otherwise a leading ORPHAN digit is merged into the group after it, so an 11-digit number
 *    reads "5551 234 567" rather than stranding a lone "5" against the country code.
 */
function groupFromRight(digits: string): string {
  if (digits.length === 10) {
    return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`;
  }

  const groups: string[] = [];
  for (let end = digits.length; end > 0; end -= 3) {
    groups.unshift(digits.slice(Math.max(0, end - 3), end));
  }

  if (groups.length > 1 && groups[0]!.length === 1) {
    groups[1] = groups[0]! + groups[1]!;
    groups.shift();
  }

  return groups.join(" ");
}

/**
 * "+21626078277" -> "+216 26 078 277".
 *
 * Anything unrecognised is returned trimmed and otherwise unchanged rather than mangled: a number
 * we cannot parse is still more useful whole than reformatted wrongly.
 */
export function formatPhone(phone: string): string {
  const trimmed = phone.trim();
  if (!trimmed) return "";

  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 6) return trimmed;

  const international = trimmed.startsWith("+") || trimmed.startsWith("00");
  if (!international) return groupFromRight(digits);

  const body = trimmed.startsWith("00") ? digits.slice(2) : digits;
  const code = COUNTRY_CODES.find((candidate) => body.startsWith(candidate));

  return code ? `+${code} ${groupFromRight(body.slice(code.length))}` : `+${groupFromRight(body)}`;
}
