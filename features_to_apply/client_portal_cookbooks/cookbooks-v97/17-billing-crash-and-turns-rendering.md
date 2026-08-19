# Cookbook 17 - Billing page crash and the `[object Object]` turns cell

Base: `version_96` @ `fa220abc85ed498bc83e158d6596d4510b87441f`.
Scope: two functional defects, both root-caused, plus regression tests. No API contract change, no new dependency, no visual change.

Apply this cookbook before 18, 19 and 20. A dead billing tab outranks every cosmetic item in the brief.

---

## 17.1 Billing page crash

### Diagnosis (see review doc section 2.1 for the full trace)

The reported text is `copy.errors.brokenTitle` / `brokenBody`, rendered only by `errorComponent` in `src/routes/__root.tsx`. That is a **render-time throw**, not a failed fetch - `billing.tsx` handles fetch failures with the inline `ErrorState` and would never produce that copy.

The throw is `RangeError: Invalid currency code` from `Intl.NumberFormat`, because:

- `me_reads.billing()` returns `"currency_code": ""` when the customer has no rows in `billing.accounts`;
- `money()` in `src/lib/format.ts` guards the amount but not the currency, and a default parameter does not cover `""`;
- `style: "currency"` requires a well-formed ISO 4217 code, so `""` throws.

Deterministic for every prepaid-only customer. Unreachable for postpaid customers, which is why it looks intermittent.

### Fix - `src/lib/format.ts`

The guard belongs here, not in `billing.tsx`. One function protects the amount-due tile, every invoice row, the invoice detail panel, and `quantity()` which delegates to `money()` for TND.

`oldStr`:

```ts
export function money(value: number | null | undefined, currency = "TND"): string {
  if (value === null || value === undefined) return "\u2014";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 3, // TND is a 3-decimal currency (millimes)
  }).format(value);
}
```

`newStr`:

```ts
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
  if (value === null || value === undefined) return "\u2014";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency: currencyOrDefault(currency),
    currencyDisplay: "code",
    minimumFractionDigits: 2,
    maximumFractionDigits: 3, // TND is a 3-decimal currency (millimes)
  }).format(value);
}
```

Note the signature widened from `currency = "TND"` to `currency: string | null | undefined`. Every existing call site already passes either nothing or a `string | null` from the API types, so this only removes casts, it does not create new ones. `quantity()` calls `money(value)` with no second argument and is unaffected.

### Fix - `src/routes/_portal/billing.tsx` (defensive, same class of bug)

Two property reads stop their optional chain one level too early:

- `billing?.invoices.items` -> `billing?.invoices?.items`
- `billing?.invoices.total` -> `billing?.invoices?.total`

The backend always sends `invoices` today, so this is not the active crash. It is one contract change away from being one, and the `?? []` / `?? 0` fallbacks already express the intent. Apply as a two-occurrence find-and-replace of `billing?.invoices.` with `billing?.invoices?.`.

Do **not** change anything else in `billing.tsx`. `PAGE_SIZE`, `qk.billing(cid, PAGE_SIZE, page * PAGE_SIZE)`, `qk.balance(cid)`, the `INVOICE_TONE` map over all seven statuses, the prepaid pointer, and the whole-account figures being independent of the invoice page are all correct and deliberate.

### Do NOT do these

- Do not default `currency_code` to `"TND"` in `me_reads.billing()`. `""` is the truthful answer for a customer with no billing account, and the backend should not invent a currency for an account that does not exist.
- Do not wrap the billing route in its own error boundary. That would hide the crash rather than fix it, and the brief explicitly forbids it.
- Do not guard at the call site in `billing.tsx` only. `services.tsx` and the invoice panel call `money()` too.

### Regression test - `src/lib/format.test.ts` (new file)

```ts
import { describe, expect, it } from "vitest";
import { money, quantity, duration } from "./format";

describe("money", () => {
  /**
   * The billing page crash: me_reads.billing() returns currency_code "" for a
   * customer with no billing accounts, and Intl.NumberFormat throws RangeError
   * on an empty currency. The throw escaped render and the customer saw
   * "This page did not load" instead of the billing page.
   */
  it("formats an amount when the API reports no currency", () => {
    expect(() => money(0, "")).not.toThrow();
    expect(money(0, "")).toContain("TND");
  });

  it("formats an amount when the currency is null or undefined", () => {
    expect(() => money(12.5, null)).not.toThrow();
    expect(() => money(12.5, undefined)).not.toThrow();
    expect(money(12.5, null)).toContain("TND");
  });

  it("rejects malformed currency codes instead of throwing", () => {
    for (const bad of ["T", "TN", "TNDX", "1ND", "  ", "tn d"]) {
      expect(() => money(1, bad)).not.toThrow();
      expect(money(1, bad)).toContain("TND");
    }
  });

  it("honours a valid currency, case-insensitively", () => {
    expect(money(1, "EUR")).toContain("EUR");
    expect(money(1, "eur")).toContain("EUR");
  });

  it("still renders a dash for a missing amount", () => {
    expect(money(null)).toBe("\u2014");
    expect(money(undefined, "TND")).toBe("\u2014");
  });

  it("keeps millime precision for TND", () => {
    expect(money(1.234, "TND")).toMatch(/1[.,]234/);
  });
});

describe("quantity", () => {
  it("delegates TND to money without throwing", () => {
    expect(() => quantity(5, "TND")).not.toThrow();
  });

  it("renders a dash for a missing value", () => {
    expect(quantity(null, "GB")).toBe("\u2014");
  });
});

describe("duration", () => {
  it("matches the activity card format", () => {
    expect(duration(129)).toBe("2m 09s");
    expect(duration(45)).toBe("45s");
    expect(duration(null)).toBe("\u2014");
  });
});
```

---

## 17.2 `[object Object]` in the conversation detail

### Diagnosis (see review doc section 2.2)

`src/routes/_portal/activity.tsx`, component `ConversationBody`:

```tsx
[copy.activity.turns, String(detail.turns)],
```

`turns` carries **two different types on two different endpoints**, and both the TS types and the backend agree:

| Endpoint | Backend | Type | Meaning |
|---|---|---|---|
| `GET /me/conversations` | `me_reads.conversations()` -> `"turns": int(row.turns)` | `number` | a count |
| `GET /me/conversations/{id}` | `me_reads.conversation_detail()` -> `"turns": [ {...} ]` | `ConversationTurn[]` | the transcript |

`String([{...}, {...}])` is `"[object Object],[object Object]"`. Eleven turns give eleven repetitions. The same component already treats it correctly as an array twelve lines lower (`detail.turns.length > 0`, `detail.turns.map(...)`).

The API contract is correct. There are no legacy shapes. This is one wrong expression.

### Fix - new file `src/lib/conversation.ts`

A named derivation, so the count is computed in one place and the divergent field name cannot trap the next reader. This is also what makes the defect testable without a DOM.

```ts
/**
 * lib/conversation.ts - reconciles the one place where the me/* API uses a
 * single field name for two different shapes.
 *
 *   GET /me/conversations        -> ConversationSummary.turns : number  (a count)
 *   GET /me/conversations/{id}   -> ConversationDetail.turns  : Turn[]  (the transcript)
 *
 * Rendering the detail shape as a scalar produced
 * "[object Object],[object Object],..." on screen. Everything that needs "how
 * many turns" goes through turnCount() so the two shapes can never be confused
 * at a call site again.
 */
import type { ConversationDetail, ConversationSummary, ConversationTurn } from "./api/activity.server";

/** Turn count for either endpoint shape. Unknown or absent data counts as 0. */
export function turnCount(
  turns: ConversationSummary["turns"] | ConversationDetail["turns"] | null | undefined,
): number {
  if (Array.isArray(turns)) return turns.length;
  return typeof turns === "number" && Number.isFinite(turns) && turns > 0 ? Math.trunc(turns) : 0;
}

/** Transcript lines for a detail payload, tolerating an absent array. */
export function turnLines(detail: Pick<ConversationDetail, "turns"> | null | undefined): ConversationTurn[] {
  return Array.isArray(detail?.turns) ? detail.turns : [];
}
```

### Fix - `src/routes/_portal/activity.tsx`

1. Add the import next to the existing `@/lib/...` imports:

```tsx
import { turnCount, turnLines } from "@/lib/conversation";
```

2. The defect itself. `oldStr`:

```tsx
    [copy.activity.turns, String(detail.turns)],
```

`newStr`:

```tsx
    [copy.activity.turns, String(turnCount(detail.turns))],
```

3. Harden the two adjacent array reads in the same component. Replace `detail.turns.length > 0` with `turnLines(detail).length > 0`, and `detail.turns.map(` with `turnLines(detail).map(`. This keeps the transcript rendering identical while removing the assumption that the array is always present.

4. Route the list-side counts through the same helper so there is exactly one definition of "how many turns". In `toItems()` replace the interpolation of `c.turns` with `turnCount(c.turns)`, and replace `String(hero.turns)` with `String(turnCount(hero.turns))`.

5. `src/routes/_portal/assistant.tsx` uses the list shape too: replace `String(lastCall.turns)` with `String(turnCount(lastCall.turns))` and add the same import. One definition, portal-wide.

### Optional type hardening in `src/lib/api/activity.server.ts`

Leave the runtime types alone - they are already accurate. If you want the compiler to catch the next occurrence, add a doc comment above `ConversationDetail`:

```ts
/**
 * NOTE: `turns` is an array here and a number on ConversationSummary. The two
 * endpoints share the field name. Use turnCount() from lib/conversation.ts for
 * any "how many" rendering - String(detail.turns) yields "[object Object]...".
 */
```

### Regression test - `src/lib/conversation.test.ts` (new file)

This asserts the exact reported symptom, not an implementation detail.

```ts
import { describe, expect, it } from "vitest";
import { turnCount, turnLines } from "./conversation";

const detailTurns = Array.from({ length: 11 }, (_, index) => ({
  index,
  speaker: index % 2 === 0 ? ("caller" as const) : ("agent" as const),
  agent: "TriageAgent",
  language: "fr",
  text: `line ${index}`,
  at: "2026-08-19T12:21:00Z",
}));

describe("turnCount", () => {
  /**
   * The exact defect: the conversation detail endpoint returns turns as an
   * array of turn objects, and the metric cell rendered String(detail.turns),
   * producing "[object Object],[object Object]" eleven times over.
   */
  it("never renders [object Object] for the detail shape", () => {
    const rendered = String(turnCount(detailTurns));
    expect(rendered).not.toContain("[object Object]");
    expect(rendered).toBe("11");
  });

  it("counts the array from the detail endpoint", () => {
    expect(turnCount(detailTurns)).toBe(11);
    expect(turnCount([])).toBe(0);
  });

  it("passes through the number from the list endpoint", () => {
    expect(turnCount(11)).toBe(11);
    expect(turnCount(0)).toBe(0);
  });

  it("treats absent, negative and non-finite values as zero", () => {
    expect(turnCount(null)).toBe(0);
    expect(turnCount(undefined)).toBe(0);
    expect(turnCount(-3)).toBe(0);
    expect(turnCount(Number.NaN)).toBe(0);
  });

  it("produces a plain integer string for any accepted input", () => {
    for (const input of [detailTurns, 11, 0, null, undefined, []] as const) {
      expect(String(turnCount(input))).toMatch(/^\d+$/);
    }
  });
});

describe("turnLines", () => {
  it("returns the transcript for a detail payload", () => {
    expect(turnLines({ turns: detailTurns })).toHaveLength(11);
  });

  it("returns an empty list when the array is absent", () => {
    expect(turnLines(null)).toEqual([]);
    expect(turnLines(undefined)).toEqual([]);
    // Malformed payload must not throw during render.
    expect(turnLines({ turns: undefined as never })).toEqual([]);
  });
});
```

---

## 17.3 Verification

Run from `Frontend/customer_portal`:

```bash
npm run typecheck        # expect 0 errors
npm test                 # expect 32 existing + ~20 new, all passing, 8 files
npx eslint src/lib/format.ts src/lib/conversation.ts src/lib/conversation.test.ts src/lib/format.test.ts src/routes/_portal/activity.tsx src/routes/_portal/billing.tsx src/routes/_portal/assistant.tsx
npm run build
bash ../../scripts/verify-portal.sh   # expect 13/13, unchanged
```

On `eslint .`: the repository currently fails it because of 10 prettier errors in the user's own uncommitted `src/lib/api/errors.ts` and untracked `errors.test.ts`. That predates this cookbook. Lint only the files you touched, or run `npx prettier --write src/lib/api/errors.ts src/lib/api/errors.test.ts` first if you want a clean whole-project run. Do not commit that formatting alongside this patch.

### Browser acceptance - billing

Use `portal-browser-check@example.tn` / `browser-check-77` (postpaid) **and** a prepaid-only account. The prepaid account is the one that reproduces the crash; a postpaid account will pass even before the fix, so testing only postpaid proves nothing.

1. Open Billing as the **prepaid** customer. Before the patch: "This page did not load". After: the page renders, amount due shows `TND 0.00`, the invoices card shows the designed empty state, and the prepaid pointer to Services is visible.
2. Open Billing as the postpaid customer: unchanged from today - real outstanding total, real next due date, invoices paged 20 at a time.
3. Loading: the amount-due tile shimmers at its own type size, the invoice list shows five skeleton rows.
4. API error: stop business-api, reload. Expect the inline `ErrorState` inside the card with a Try again button - **not** the whole-page error. If you get the whole-page error, something is still throwing in render.
5. Auth failure: clear the session cookie, reload. Expect a redirect to `/login`, not an error page.
6. Malformed response: this is what the `billing?.invoices?.` chain covers. Confirm no crash.
7. Refresh, then navigate away and back. Paging state resets to page 1, no stale rows.
8. Responsive at 1440 / 1024 / 390 wide, and at 700px tall.
9. Dark mode now; light mode after cookbook 20.

### Browser acceptance - conversation detail

1. Activity tab, open any previous conversation with turns. The `turns` cell must read `11`, not `[object Object]...`.
2. The transcript below must be unchanged: speaker labels via `copy.labels.speaker`, persona via `personaLabel`, masked text, timestamps.
3. Open a conversation with **zero** turns. The cell must read `0` and the transcript block must be absent, not a broken empty list.
4. Confirm the Activity list cards and the hero tile still show the same counts as before - they now go through `turnCount` but the list shape is a number, so the values must be identical.
5. Confirm the assistant post-call summary turn count still matches.

### Definition of done for cookbook 17

- Billing renders for prepaid-only customers. No RangeError, no whole-page error boundary.
- Billing still renders correctly for postpaid customers, with paging intact.
- Fetch failures still show the inline section error, never the page error.
- The conversation detail turns cell shows a real integer.
- The transcript, list counts, hero tile and assistant summary are unchanged.
- `turnCount` is the single definition of "how many turns" in the portal.
- Two new test files lock both defects. Typecheck, targeted lint, build and verify-portal all clean.
