# Cookbook 14 - Runtime proof and the regression tests that make silent divergence impossible

**Target branch:** version_95
**Files added:** 3 test files. **Files modified:** 1 (ci.yml). **Backend logic:** none. **Migrations:** none.

Two halves. Section 1 adds the automated tests that would have caught the version_94 offset bug before it shipped. Section 2 is the runtime proof that has still never been executed anywhere - no live call has ever been made against this portal code.

---

## 14.1 Why this cookbook exists

The version_94 results document reported, in good faith:

> Windowed: .offset(start).limit(size) - PASS

The branch has `.limit(size)` and no offset. The check that was actually run was "the route accepts an offset parameter without returning 422", which passes on broken code. Every projection assertion so far has been of that shape: a grep, a signature, or a status code. None of them compares two pages of rows.

So the rule from here on: **a pagination claim is only evidence if two different pages are fetched and their contents compared.** Sections 14.2 and 14.3 encode that as tests, so no future results document can report a pass that the code does not earn.

---

## 14.2 Backend regression tests for the read projections

New file `apps/business-api/tests/test_me_reads_paging.py`. It follows the fixture style already used by `test_auth_http.py` - adapt the session fixture name to whatever that file imports.

```python
"""Paging contract tests for the portal read projections.

These exist because version_94 shipped notifications() and callbacks() that
reported an offset in the envelope and never applied it to the query. Every
test here fetches two different pages and compares rows: a test that only
asserts "the parameter is accepted" passes on that bug.
"""
from __future__ import annotations

import pytest

from business_api import me_reads


def _rows(payload: dict) -> list[tuple]:
    """Identity of a row, independent of key order."""
    return [tuple(sorted(item.items(), key=lambda kv: kv[0])) for item in payload["items"]]


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_pages_do_not_overlap(session, seeded_customer_id, reader):
    """Page 2 must not repeat page 1. This is the version_94 regression."""
    first = reader(session, customer_id=seeded_customer_id, limit=2, offset=0)
    second = reader(session, customer_id=seeded_customer_id, limit=2, offset=2)

    if first["total"] < 4:
        pytest.skip("seed does not have enough rows for this projection")

    assert set(_rows(first)).isdisjoint(set(_rows(second)))


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_walking_pages_yields_every_row_exactly_once(session, seeded_customer_id, reader):
    """A total order plus a correct offset means the union of the pages is the
    whole set, with no duplicates and nothing skipped."""
    total = reader(session, customer_id=seeded_customer_id, limit=1, offset=0)["total"]
    seen: list[tuple] = []
    for offset in range(0, total, 3):
        seen.extend(_rows(reader(session, customer_id=seeded_customer_id, limit=3, offset=offset)))

    assert len(seen) == total
    assert len(set(seen)) == total


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_total_is_independent_of_the_page(session, seeded_customer_id, reader):
    """total counts the set, not the window."""
    a = reader(session, customer_id=seeded_customer_id, limit=1, offset=0)
    b = reader(session, customer_id=seeded_customer_id, limit=50, offset=0)
    assert a["total"] == b["total"]


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_envelope_echoes_the_window_it_applied(session, seeded_customer_id, reader):
    payload = reader(session, customer_id=seeded_customer_id, limit=5, offset=5)
    assert payload["limit"] == 5
    assert payload["offset"] == 5
    assert len(payload["items"]) <= 5


def test_offset_beyond_the_end_is_empty_not_an_error(session, seeded_customer_id):
    payload = me_reads.notifications(session, customer_id=seeded_customer_id, limit=5, offset=10_000)
    assert payload["items"] == []
    assert payload["total"] > 0


def test_limit_is_clamped_to_page_max(session, seeded_customer_id):
    payload = me_reads.notifications(session, customer_id=seeded_customer_id, limit=10_000, offset=0)
    assert payload["limit"] == me_reads._PAGE_MAX


def test_negative_offset_is_treated_as_zero(session, seeded_customer_id):
    payload = me_reads.notifications(session, customer_id=seeded_customer_id, limit=5, offset=-20)
    assert payload["offset"] == 0


def test_billing_totals_do_not_follow_the_invoice_page(session, seeded_customer_id):
    """total_outstanding and next_due_date are account-wide (CB9, CB12 12.2)."""
    page_one = me_reads.billing(session, customer_id=seeded_customer_id, limit=1, offset=0)
    page_two = me_reads.billing(session, customer_id=seeded_customer_id, limit=1, offset=1)

    assert page_one["total_outstanding"] == page_two["total_outstanding"]
    assert page_one["next_due_date"] == page_two["next_due_date"]
    assert page_one["invoices"]["total"] == page_two["invoices"]["total"]
    if page_one["invoices"]["total"] > 1:
        assert page_one["invoices"]["items"] != page_two["invoices"]["items"]


def test_conversation_turns_are_chronological(session, seeded_customer_id):
    """CB8.4: created_at, never speaker, is the tiebreak inside a turn index."""
    listing = me_reads.conversations(session, customer_id=seeded_customer_id, limit=50, offset=0)
    for summary in listing["items"]:
        detail = me_reads.conversation_detail(
            session,
            customer_id=seeded_customer_id,
            session_id=summary["session_id"],
        )
        if detail is None or len(detail["turns"]) < 2:
            continue
        stamps = [turn["at"] for turn in detail["turns"] if turn["at"]]
        assert stamps == sorted(stamps)
        return
    pytest.skip("no seeded conversation with two or more turns")
```

### A second test file for the boundary that matters most

New file `apps/business-api/tests/test_me_reads_isolation.py`. Ownership is the portal's one hard security property and nothing asserts it today.

```python
"""Cross-customer isolation for every portal read projection.

The invariant in me_reads' own docstring is that customer_id always arrives
from Principal.customer_id and every {id} lookup re-checks ownership. These
tests are what make that a fact rather than a comment.
"""
from __future__ import annotations

import pytest

from business_api import me_reads

LIST_READERS = [
    me_reads.notifications,
    me_reads.callbacks,
    me_reads.conversations,
    me_reads.requests,
]


@pytest.mark.parametrize("reader", LIST_READERS)
def test_reader_returns_nothing_for_an_unrelated_customer(session, other_customer_id, reader):
    """A customer with no rows of their own must get an empty, well-formed
    envelope - never another customer's rows."""
    payload = reader(session, customer_id=other_customer_id, limit=50, offset=0)
    assert payload["total"] == len(payload["items"])


def test_conversation_detail_hides_another_customers_session(
    session, seeded_customer_id, other_customer_id
):
    """Another customer's session_id must be indistinguishable from a
    nonexistent one: both return None so the route answers 404, not 403."""
    mine = me_reads.conversations(session, customer_id=seeded_customer_id, limit=1, offset=0)
    if not mine["items"]:
        pytest.skip("no seeded conversation")
    session_id = mine["items"][0]["session_id"]

    assert (
        me_reads.conversation_detail(
            session, customer_id=other_customer_id, session_id=session_id
        )
        is None
    )


def test_no_projection_leaks_a_forbidden_key(session, seeded_customer_id):
    """The forbidden-key list, enforced in code instead of by grep. vip is on
    this list per CB12 12.5.4: it is internal segmentation."""
    forbidden = {
        "frustration",
        "max_frustration",
        "sentiment",
        "token_digest",
        "failure_reason",
        "audio_record_url",
        "recording_consent",
        "has_recording",
        "customer_vip",
        "vip",
        "last_synced_at",
        "outcome_note",
        "transaction_reference",
        "detected_intent",
        "attempts",
    }

    payloads = [
        me_reads.notifications(session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.callbacks(session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.conversations(session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.requests(session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.billing(session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.balance(session, customer_id=seeded_customer_id),
    ]

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                assert key not in forbidden, f"forbidden key {key} in a portal projection"
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in payloads:
        walk(payload)
```

The `vip` entry is the reason this test is worth more than the grep it replaces: the grep looks for `customer_vip` and the projection field is `vip`, which is how it reached the customer's Profile page unnoticed.

### Frontend unit test for the paging control

New file `Frontend/customer_portal/src/components/portal/pagination.test.ts`, next to the existing `copy.test.ts` and `tool-events.test.ts`. Export `pageWindow` from `data.tsx` to make it testable (it is currently module-private):

```ts
import { describe, expect, it } from "vitest";
import { pageWindow } from "@/components/portal/data";

describe("pageWindow", () => {
  it("lists every page when there are few", () => {
    expect(pageWindow(1, 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("always includes first, last and current", () => {
    const out = pageWindow(6, 12);
    expect(out).toContain(1);
    expect(out).toContain(12);
    expect(out).toContain(6);
  });

  it("never renders two gaps in a row", () => {
    const out = pageWindow(6, 40).map(String);
    expect(out.join(",")).not.toContain("gap,gap");
  });

  it("stays inside the range at both ends", () => {
    for (const current of [1, 2, 39, 40]) {
      const numbers = pageWindow(current, 40).filter((p): p is number => typeof p === "number");
      expect(Math.min(...numbers)).toBeGreaterThanOrEqual(1);
      expect(Math.max(...numbers)).toBeLessThanOrEqual(40);
    }
  });
});
```

### Wire them in

The backend tests are collected by the existing `pytest apps/business-api/tests` invocation and by `scripts/run_tests.py`; nothing to configure. The frontend test is picked up by vitest automatically. If `session`, `seeded_customer_id` or `other_customer_id` fixtures do not exist yet, add them to the existing `conftest.py` beside the fixtures `test_auth_http.py` already uses - `other_customer_id` should be the second demo customer (Karim Gharbi, CIN 2256) so isolation is tested against real seeded data.

---

## 14.3 CI: make the offset class of bug unshippable

In `.github/workflows/ci.yml`, the `test` job already runs the backend suite, so the new files are covered there. Two additions.

In `customer-portal-test`, the `Guard (verify-portal.sh)` step landed in version_94 and its first real execution is still pending. Leave it exactly where it is - between Lint and Test - and expect the first run on version_95 to fail. When it does, read the failing check name and fix the code it names; do not weaken the script.

Add one grep-based guard to `scripts/verify-portal.sh`, as check 13, because it is the cheapest possible defence against the exact regression:

```bash
# 13. Any projection that reports an offset must apply one. A function that
#     resolves _page(limit, offset) and never calls .offset() is the version_94
#     notifications()/callbacks() bug.
if grep -n "_page(limit, offset)" ../../apps/business-api/src/business_api/me_reads.py >/dev/null; then
  missing=$(python3 - <<'PY'
import re, pathlib
src = pathlib.Path("../../apps/business-api/src/business_api/me_reads.py").read_text()
bad = []
for block in re.split(r"\ndef ", src):
    if "_page(limit, offset)" in block and ".offset(start)" not in block:
        bad.append(block.split("(")[0].strip())
print(",".join(bad))
PY
)
  if [ -n "$missing" ]; then
    echo "FAIL 13: these readers resolve a page window but never apply it: $missing"
    exit 1
  fi
fi
echo "PASS 13: every paged reader applies its offset"
```

Adjust the relative path to match where the script runs from (`Frontend/customer_portal`). If you would rather keep the guard script frontend-only, put this check in the `test` job as a one-line python step instead - the location matters less than its existence.

---

## 14.4 Runtime proof - still never executed

Everything below has been specified twice (CB7, CB11) and run zero times. Docker is up per your last report, so the only missing piece is the LiveKit stack plus the agent worker. This is the shortest path to "works with no problems" being a finding rather than a hope.

### Step 1 - stack up, schema current

```bash
docker compose up -d
docker compose exec business-api alembic upgrade head
docker compose ps
```

Expect: every service `Up (healthy)`; alembic reports head `0017_notification_failure_reason` with nothing to apply.

### Step 2 - suites

```bash
pytest apps/business-api/tests -q
pytest apps/token-service/tests -q
python scripts/run_tests.py
cd Frontend/customer_portal && npm run typecheck && npm run lint && npm run verify && npm test && npm run build
```

Expect: the four new paging/isolation test files green; `run_tests.py` all suites green; `npm run verify` executing 13 checks for the first time on real bash.

### Step 3 - auth paths, with real status codes

| Case | How | Expect |
|---|---|---|
| Sign in | demo client credentials | 200, session cookie set, portal renders |
| Wrong password | same email, bad password | 401 and the portal's own wording, not a stack trace |
| Lockout | 5 failed attempts (MAX_FAILED_ATTEMPTS) | 6th returns 429; unlocks after 15 minutes (LOCKOUT_MINUTES) |
| Staff token on a client route | staff bearer on /api/v1/me/profile | 403 |
| Client token on an advisor route | client bearer on an advisor endpoint | 403 |
| Another customer's session id | /me/conversations/{id} with a foreign id | 404, never 403 |
| Revoke all | Security tab, revoke-all | other sessions dead on next request; current one survives |
| Expired session | wait past PORTAL_SESSION_TTL | redirect to login, no blank page |

Rotate `test-client-403@example.tn` / `client-secret-test-55` after this run - it is in the repo history.

### Step 4 - one live call, all nine orb states

Open /assistant and make a real call. Watch for, in order: `disconnected`, `connecting`, `preConnect` (the `pre-connect-buffering` mapping), `initializing`, `idle`, `listening`, `thinking`, `speaking`, back to `disconnected`. Then:

- ask something that triggers a read tool (`get_balance_summary`) - the timeline row must appear in customer wording, pending then done, on topic `telecom.tool-events`
- confirm at most 3 visible rows at opacity 1 / 0.52 / 0.22
- confirm the customer's own name and the agent pseudonym render, not raw identities
- confirm messages fade in and old ones fade out as they did in apps/client-widget
- **confirm the agent greets the signed-in customer, not the pilot subscriber** - this is the end-to-end proof of the CB8.1 key path; if it greets the pilot, `INTERNAL_API_KEY` is missing or mismatched between the portal and token-service
- end the call: the summary must resolve a real duration and a real turn count within about 6 seconds (CB8.5), and the call must appear in Activity without a reload even though no write tool ran

### Step 5 - data pages against the seeded census

129 sessions, 490 turns, 21 tickets, 48 notifications, 2 invoices, 2 billing accounts.

| Page | Check |
|---|---|
| Activity | 129 total; page 2 rows differ from page 1; last page partial; transcript panel opens, traps focus, restores it on Escape |
| Requests | 21 total; status filter resets to page 1; counts match the filter |
| Billing | amount due matches the SQL sum; due date does not change while paging; 2 invoices |
| Services | prepaid credit in TND, every balance type, top-up list (CB13) |
| Security | current session flagged; revoke-all works |
| Profile | scoped cache key; no VERIFIED/UNVERIFIED chips; no VIP chip (CB12 12.5) |
| Help | 5 deep links plus 2 exits, all navigating |

### Step 6 - responsive and reduced motion

1440, 1024 and 390 px. No horizontal scroll, no cell under 44 px tall, no overlap, tiles reflowing 3 to 1. Then enable OS reduce-motion: `TopProgress` stops sliding, `AnimatedTabs` stops animating, no layout breaks.

### Step 7 - build hygiene

```bash
cd Frontend/customer_portal && npm run build
grep -Rn "8107\|TOKEN_SERVICE\|LIVEKIT_API\|PORTAL_SESSION\|INTERNAL_API_KEY\|x-internal-api-key" .output/public || echo "clean"
```

Expect `clean`. Any hit is a server secret in a browser bundle.

### Step 8 - the open ruff/mypy question

The first CI run on version_95 settles whether the committed `repositories.py` and `persistence/models/__init__.py` trip the root `ruff`/`mypy` configuration, which no local run has been able to answer. Read the `lint` job output and record the verdict; if it fails, that is a separate cookbook and not something to fix inside a portal patch.

---

## 14.5 What to report back

For each of the eight steps: the command, the actual output, and pass or fail. For anything that fails, the failure text rather than a summary of it. Where a check cannot be run, say "not run" - that is genuinely useful, and it is the one thing the previous three results documents got exactly right about CB11.

The standard, restated: an assertion counts as evidence only if it could have failed on broken code. "The route accepted the parameter" could not. "Page 2 differs from page 1" can.
