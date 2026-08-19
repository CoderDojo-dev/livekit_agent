# Cookbook 16 — Topbar cache key fix and the missing regression tests

**Target branch:** version_96
**Files changed:** 3. **Backend logic:** none. **Migrations:** none. **New dependency:** none.

Two items. Both are small. Neither touches the orb, styles.css, or any backend model.

---

## 16.1 Fix the unscoped profile key in portal-topbar.tsx

### What is wrong

`portal-topbar.tsx` queries `/me/profile/detail` under the key `["me", "profile", "detail"]`.
`profile.tsx` queries the same endpoint under `qk.profileDetail(cid)` = `["me", cid, "profile-detail"]`.

These are two separate cache entries. Two fetches on every profile-page load. More importantly: the logout sweep that calls `queryClient.removeQueries({ queryKey: ["me", customerId] })` does not match the topbar key, so it survives sign-out and shows the previous account's name until a focus-triggered refetch replaces it. On a same-tab account switch (sign out as Yousra, sign in as Amine) the topbar renders Yousra's full name.

### Fix

In `portal-topbar.tsx`, replace the three lines that define the profile query:

```ts
  // Before
  const profile = useQuery({
    queryKey: ["me", "profile", "detail"],
    queryFn: () => fetchProfileDetail(),
  });
```

with:

```ts
  // After
  const profile = useQuery({
    queryKey: qk.profileDetail(session?.customerId ?? "unknown"),
    queryFn: () => fetchProfileDetail(),
    staleTime: 30_000,
  });
```

Also add the `qk` import at the top of the file, alongside the existing imports:

```ts
import { qk } from "@/lib/query-keys";
```

The `session` object is already in scope (the file already calls `usePortalSession()`). `staleTime: 30_000` matches profile.tsx and prevents the topbar from making a separate network request on every navigation within the portal while the data is fresh.

### What changes at runtime

- One cache entry instead of two for profile data.
- The topbar and the profile page share the same React Query dedup: if profile.tsx already fetched, the topbar renders immediately from cache, and vice versa.
- The topbar key is now swept on logout with everything else.
- Account switch: after sign-out the profile entry is gone; the new account's name loads fresh.

### Acceptance checks

| # | Check | Pass condition |
|---|---|---|
| 1 | Single cache entry | React Query devtools shows one `["me", cid, "profile-detail"]` entry, not two |
| 2 | No extra network call | Open Network tab, navigate /profile -> / -> /profile; profile/detail called once, not twice |
| 3 | Logout sweeps it | Sign out; React Query devtools shows no `["me", ...]` entries |
| 4 | Cross-account | Sign in as Yousra; sign out; sign in as Amine; topbar shows Amine's name immediately |
| 5 | Typecheck and lint | 0 errors |

---

## 16.2 Commit the missing regression tests

CB14 specified and CB15 locally ran 27 backend regression tests. Neither test file exists in the version_95 tree. The 27 assertions that make the pagination-offset class of bug unshippable live only in the local container and will be lost on the next `docker compose up` recreate.

Add the two files verbatim from cookbook 14. They are reproduced here in full so no lookup is needed.

### apps/business-api/tests/test_me_reads_paging.py

```python
"""Paging contract tests for the portal read projections.

These exist because version_94 shipped notifications() and callbacks() that
reported an offset in the envelope and never applied it to the query. Every
test here fetches two different pages and compares rows: a test that only
asserts 'the parameter is accepted' passes on that bug.
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
def test_pages_do_not_overlap(db_session, seeded_customer_id, reader):
    """Page 2 must not repeat page 1. This is the version_94 regression."""
    first = reader(db_session, customer_id=seeded_customer_id, limit=2, offset=0)
    second = reader(db_session, customer_id=seeded_customer_id, limit=2, offset=2)

    if first["total"] < 4:
        pytest.skip("seed does not have enough rows for this projection")

    assert set(_rows(first)).isdisjoint(set(_rows(second)))


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_walking_pages_yields_every_row_exactly_once(db_session, seeded_customer_id, reader):
    """A total order plus a correct offset means the union of the pages is the
    whole set, with no duplicates and nothing skipped."""
    total = reader(db_session, customer_id=seeded_customer_id, limit=1, offset=0)["total"]
    seen: list[tuple] = []
    for offset in range(0, total, 3):
        seen.extend(_rows(reader(db_session, customer_id=seeded_customer_id, limit=3, offset=offset)))

    assert len(seen) == total
    assert len(set(seen)) == total


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_total_is_independent_of_the_page(db_session, seeded_customer_id, reader):
    """total counts the set, not the window."""
    a = reader(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    b = reader(db_session, customer_id=seeded_customer_id, limit=50, offset=0)
    assert a["total"] == b["total"]


@pytest.mark.parametrize(
    "reader",
    [me_reads.notifications, me_reads.callbacks, me_reads.conversations, me_reads.requests],
)
def test_envelope_echoes_the_window_it_applied(db_session, seeded_customer_id, reader):
    payload = reader(db_session, customer_id=seeded_customer_id, limit=5, offset=5)
    assert payload["limit"] == 5
    assert payload["offset"] == 5
    assert len(payload["items"]) <= 5


def test_offset_beyond_the_end_is_empty_not_an_error(db_session, seeded_customer_id):
    payload = me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=5, offset=10_000)
    assert payload["items"] == []
    assert payload["total"] > 0


def test_limit_is_clamped_to_page_max(db_session, seeded_customer_id):
    payload = me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=10_000, offset=0)
    assert payload["limit"] == me_reads._PAGE_MAX


def test_negative_offset_is_treated_as_zero(db_session, seeded_customer_id):
    payload = me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=5, offset=-20)
    assert payload["offset"] == 0


def test_billing_totals_do_not_follow_the_invoice_page(db_session, seeded_customer_id):
    """total_outstanding and next_due_date are account-wide (CB9, CB12 12.2)."""
    page_one = me_reads.billing(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    page_two = me_reads.billing(db_session, customer_id=seeded_customer_id, limit=1, offset=1)

    assert page_one["total_outstanding"] == page_two["total_outstanding"]
    assert page_one["next_due_date"] == page_two["next_due_date"]
    assert page_one["invoices"]["total"] == page_two["invoices"]["total"]
    if page_one["invoices"]["total"] > 1:
        assert page_one["invoices"]["items"] != page_two["invoices"]["items"]


def test_conversation_turns_are_chronological(db_session, seeded_customer_id):
    """CB8.4: turn_index asc, then created_at asc, is the sort order."""
    listing = me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=50, offset=0)
    for summary in listing["items"]:
        detail = me_reads.conversation_detail(
            db_session,
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

Note: the fixture name is `db_session`, matching the existing conftest.py (the results doc applied this adaptation locally; use whatever name conftest.py exports).

### apps/business-api/tests/test_me_reads_isolation.py

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
def test_reader_returns_nothing_for_an_unrelated_customer(db_session, other_customer_id, reader):
    """A customer with no rows of their own must get an empty, well-formed
    envelope - never another customer's rows."""
    payload = reader(db_session, customer_id=other_customer_id, limit=50, offset=0)
    assert payload["total"] == len(payload["items"])


def test_conversation_detail_hides_another_customers_session(
    db_session, seeded_customer_id, other_customer_id
):
    """Another customer's session_id must be indistinguishable from a
    nonexistent one: both return None so the route answers 404, not 403."""
    mine = me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=1, offset=0)
    if not mine["items"]:
        pytest.skip("no seeded conversation")
    session_id = mine["items"][0]["session_id"]

    assert (
        me_reads.conversation_detail(
            db_session, customer_id=other_customer_id, session_id=session_id
        )
        is None
    )


def test_no_projection_leaks_a_forbidden_key(db_session, seeded_customer_id):
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
        me_reads.notifications(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.callbacks(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.conversations(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.requests(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.billing(db_session, customer_id=seeded_customer_id, limit=50, offset=0),
        me_reads.balance(db_session, customer_id=seeded_customer_id),
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

### Why the fixture is `db_session` not `session`

The existing `conftest.py` in `apps/business-api/tests/` exports `db_session` (the results doc noted this when adapting CB14). If your conftest exports a different name, use that. Do not rename the fixture — adapt the test import. The `seeded_customer_id` and `other_customer_id` fixtures were added to conftest in v95 (Amine Ben Salah national_id `11224087` and Karim Gharbi CIN `55662256` respectively); they are already present on the branch.

### Wire into CI

No ci.yml change needed. The test job already runs `pytest apps/business-api/tests` and pytest collects every `test_*.py` file automatically.

### Acceptance checks

| # | Check | Pass condition |
|---|---|---|
| 1 | Files exist | `git ls-files apps/business-api/tests/test_me_reads_paging.py apps/business-api/tests/test_me_reads_isolation.py` — two lines |
| 2 | Tests collected | `pytest apps/business-api/tests/test_me_reads_paging.py --collect-only` — 18 items |
| 3 | All pass | `pytest apps/business-api/tests/test_me_reads_paging.py apps/business-api/tests/test_me_reads_isolation.py -q` — 27 passed |
| 4 | Breaking-change proof | Introduce a version_94-style bug by removing `.offset(start)` from one reader and re-running; test_pages_do_not_overlap must FAIL | re-add the offset before committing |
| 5 | CI green | Push; the `test` job in ci.yml must include the 27 new tests in its count |

---

## 16.3 Rollback

| Change | Revert | Consequence |
|---|---|---|
| 16.1 topbar key | restore the three original lines | cross-account name bleed and duplicate fetch return |
| 16.2 test files | delete the two files | 27 regression tests stop running; the offset class of bug becomes undetectable again |
