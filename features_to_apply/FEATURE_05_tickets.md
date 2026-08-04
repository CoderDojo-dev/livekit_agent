# Feature 5 — Ticket Management (`/tickets`)

> **Cookbook 5 of the admin-dashboard integration series.**
> Target branch: local `version_80` (HEAD `eda5f58`). Source of truth: `chouaib-saad/livekit_agent` @ `eda5f58ff3f468755db455e445eb6117b6909b5c`.
> Builds on the applied substrate of Feature 0 (integration), 1 (advisors), 2 (availability), 3 (callbacks), 4 (call logs).

---

## 0. Read this first — the architecture question, and its answer

At the end of Cookbook 4 I flagged that Tickets would need a decision from you: does `business-api` gain a read-through to GLPI, or does the admin view scope down to what the platform already persists?

**The extraction answered it, and it did not need your arbitration.** From `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/mirror.py`, verbatim module docstring:

> *"GLPI stays the source of truth, but the mirror is what makes tickets durable across restarts, answerable in real time on the voice path, and **readable by a future supervisor UI from ONE clean table (ticketing.tickets)**."*

The system was **designed** for this dashboard to read `ticketing.tickets` directly. That table lives in the same Postgres that `business-api` already connects to, and `Ticket` is **already imported** in `repositories.py` and already used by `customer_360`. So reads need no MCP client, no GLPI credentials in `business-api`, and no new network path.

The corollary is the hard part, and it is not negotiable:

**Reads come from the mirror. Writes must never.** Every mutating tool in `glpi_ticket_ops.py` writes **GLPI first, then the mirror**, in that order. If the dashboard wrote the mirror directly, the two would diverge — and it is worse than a stale row, because `upsert_from_glpi()` **writes the GLPI status back over the mirror** on the next lookup. An admin's edit would apply, look successful, and then **silently vanish** the next time any caller asked about that ticket. That is the single most dangerous thing this cookbook prevents. See §4 F3 and §8.1.

So Feature 5 is **read-only supervision**, exactly like Feature 4, and for a much sharper reason.

---

## 1. Feature name & scope

**Feature:** Ticket Management — the supervision view over every support ticket the platform knows about: what was raised, for whom, how urgent, what state it is in, and how fresh our copy is.

### In scope

| Capability | Backing data | Status |
|---|---|---|
| Paginated ticket list, newest first | `ticketing.tickets` | **new endpoint** (§3) |
| Customer identity per row | `crm.customers` join | **new endpoint** |
| Filter by status / category / priority | mirror columns | **new endpoint** |
| Search by subject or GLPI id | `subject`, `glpi_ticket_id` | **new endpoint** |
| Status counts across the whole table | `GROUP BY status` | **new endpoint** |
| Sync freshness per row | `last_synced_at` | **new endpoint** |

### Explicitly out of scope

| Not built | Reason |
|---|---|
| Create ticket ("New ticket" button) | **Sends the customer a WhatsApp message.** §4 F10 — the most dangerous button in the template |
| Edit / resolve / close / delete | Must go GLPI-first through MCP; writing the mirror directly produces edits that later vanish. §8.1 |
| Assign to advisor | **No assignee column exists** anywhere in the mirror or the MCP tools. §4 F7 |
| Ticket detail drawer | **`description` is never mirrored** — it exists only inside GLPI. §4 F17 |
| Tickets never seen by the platform | Mirror holds only what the platform touched or reconciled. §4 F2 |

### Route status — zero navigation churn (third feature running)

`/tickets` already exists in `nav.ts` and `routeTree.gen.ts`. **`routeTree.gen.ts` must diff empty.** No nav entry, no `PAGE_META`, no shortcut.

---

## 2. Backend reference (exact names & paths)

### 2.1 `packages/persistence/src/persistence/models/ticketing.py` (`679307ab`)

Module docstring: *"Ticketing schema (spec section 10): a thin local mirror of GLPI (GLPI stays source of truth)."*

```python
class Ticket(UUIDPrimaryKey, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "category IN ('network_complaint','formal_complaint','technical','billing','other')",
            name="category",
        ),
        CheckConstraint(
            "status IN ('open','in_progress','pending','resolved','closed')", name="status"
        ),
        CheckConstraint("priority IS NULL OR priority IN ('low','medium','high','urgent')", name="priority"),
        {"schema": "ticketing"},
    )
```

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | internal only — **never shown**; GLPI id is the human identifier |
| `glpi_ticket_id` | `String(40)` **NOT NULL UNIQUE** | the display id |
| `customer_id` | FK → `crm.customers`, indexed | **nullable** |
| `subscription_id` | FK | nullable |
| `category` | `String(40)` NOT NULL, default `'other'` | 5-value vocabulary |
| `subject` | `String(255)` | **nullable** |
| `status` | `String(20)` NOT NULL, default `'open'` | 5-value vocabulary |
| `priority` | `String(10)` | **nullable** — 4-value vocabulary |
| `last_synced_at` | timestamptz NOT NULL | when we last agreed with GLPI |
| `created_at` | timestamptz NOT NULL | |

**There is no `updated_at`, no `assignee`, no `description`, no `resolution`.** Four columns the mock assumes, none of which exist.

### 2.2 `mcp-servers/ticketing-glpi/src/ticketing_glpi/adapters/mirror.py` (`cf1f7428`)

The sanctioned row shape — **our endpoint reuses these exact key names** so the platform speaks one ticket dialect:

```python
def _row_to_dict(row) -> dict:
    """Shape a Ticket row for tool responses (the shape the agent and a future UI consume)."""
    return {
        "ticket_id": row.glpi_ticket_id,
        "status": row.status,
        "subject": row.subject,
        "category": row.category,
        "priority": row.priority,
        "customer_id": str(row.customer_id) if row.customer_id else None,
        "subscription_id": str(row.subscription_id) if row.subscription_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
    }
```

Vocabularies (authoritative, and they match the DB constraints exactly):

```python
_ALLOWED_CATEGORIES = {"network_complaint", "formal_complaint", "technical", "billing", "other"}
_ALLOWED_STATUS = {"open", "in_progress", "pending", "resolved", "closed"}
_ALLOWED_PRIORITY = {"low", "medium", "high", "urgent"}
```

Every mirror function is **best-effort**: gated on `_enabled()` (`DATABASE_URL` present) and wrapped in `try/except` that only calls `logger.warning(...)`. **A mirror write can fail silently.** This is the honesty constraint behind §4 F2.

`read_for_customer` orders `Ticket.created_at.desc()` — newest first. We match it.

### 2.3 `mcp-servers/ticketing-glpi/src/ticketing_glpi/tools/glpi_ticket_ops.py` (`f61197b9`)

Module docstring, verbatim and load-bearing:

> *"GLPI is the source of truth; the Postgres mirror (adapters/mirror.py) is the durable local projection the agent reads on the voice path and **a future UI reads for CRUD**. **Every write goes to GLPI first, then the mirror**, so the two stay consistent; every read prefers the mirror and reconciles from GLPI when the mirror is cold, so an admin's GLPI-side status change is reflected back to the caller on a later turn."*

Tools exposed (`server.py`, MCP streamable HTTP on **:8202**, path `/mcp`): `create_ticket`, `get_ticket_status`, `update_ticket`, `resolve_ticket`, `close_ticket`, `delete_ticket`, `lookup_tickets`, `ensure_customer_glpi_user`.

`create_ticket` — note what it does **after** filing:

```python
            resp = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/notify",
                json={
                    "customer_id": customer_id,
                    "channel": "whatsapp",
                    "template": "ticket_created",
                    "language": language,
                    "params": {"ticket_id": ticket.ticket_id},
                },
```

**Creating a ticket texts the customer on WhatsApp.** §4 F10.

### 2.4 `business_api/repositories.py` (`0f9acd1f`) — what exists today

`Ticket` is already imported. The only ticket read is nested inside `customer_360`:

```python
            "tickets": [{"glpi_id": t.glpi_ticket_id, "status": t.status, "subject": t.subject} for t in tickets],
```

Three fields, one customer at a time, no priority, no category, no dates. Not a list surface.

---

## 3. Endpoints

### 3.0 Contract table

| Method | Path | Min role | Status |
|---|---|---|---|
| `GET` | `/api/v1/tickets` | **`superviseur`** | **NEW** |
| `GET` | `/api/v1/customers/{id}/360` | `conseiller` | existing, untouched |

`superviseur` for the same reason as Feature 4's session index: browsing every ticket in the estate is supervision, while `conseiller` reads are single-record and need-to-know. `require_role` is minimum-rank, so the dashboard's `administrateur` session passes — **still declare the exact contract role** (Feature 2 decision #1).

### 3.1 New repository method

**File:** `apps/business-api/src/business_api/repositories.py`
**Placement:** immediately after `customer_360`, before `session_detail`. No existing line changes. **Zero new imports** — `select`, `func`, `Ticket`, `Customer`, `to_uuid` are all already at the top of the file.

```python
    def ticket_list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        customer_id: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Paginated view over the local GLPI mirror (ticketing.tickets).

        Read-only. GLPI remains the source of truth; this exposes the durable local projection
        the mirror was built to serve, and reports last_synced_at so the reader can judge how
        fresh that projection is.
        """
        stmt = select(Ticket)
        count_stmt = select(func.count()).select_from(Ticket)

        def _both(clause):
            nonlocal stmt, count_stmt
            stmt = stmt.where(clause)
            count_stmt = count_stmt.where(clause)

        if status:
            _both(Ticket.status == status)
        if category:
            _both(Ticket.category == category)
        if priority:
            _both(Ticket.priority == priority)

        cid = to_uuid(customer_id) if customer_id else None
        if cid is not None:
            _both(Ticket.customer_id == cid)

        if search:
            like = f"%{search.strip()}%"
            _both(Ticket.subject.ilike(like) | Ticket.glpi_ticket_id.ilike(like))

        total = self._s.scalar(count_stmt) or 0
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        rows = self._s.scalars(
            stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)
        ).all()

        customer_ids = {r.customer_id for r in rows if r.customer_id}
        customers = {}
        if customer_ids:
            customers = {
                c.id: c
                for c in self._s.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
            }

        # Whole-table status counts, independent of the current page and of the status filter.
        counts = {
            row[0]: row[1]
            for row in self._s.execute(
                select(Ticket.status, func.count()).group_by(Ticket.status)
            ).all()
        }

        items = []
        for r in rows:
            customer = customers.get(r.customer_id)
            items.append({
                "ticket_id": r.glpi_ticket_id,
                "status": r.status,
                "subject": r.subject,
                "category": r.category,
                "priority": r.priority,
                "customer_id": str(r.customer_id) if r.customer_id else None,
                "customer_name": f"{customer.first_name} {customer.last_name}".strip() if customer else None,
                "customer_vip": bool(customer.vip_flag) if customer else False,
                "subscription_id": str(r.subscription_id) if r.subscription_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
            })

        return {"tickets": items, "total": total, "counts": counts, "limit": limit, "offset": offset}
```

**Deliberate choices:**

- **Key names mirror `_row_to_dict` exactly**, plus `customer_name` / `customer_vip`. One ticket dialect across agent, MCP and dashboard.
- **`counts` is whole-table and ignores the status filter**, so the status chips keep showing the full picture while you are filtered into one of them. That is what makes them useful as navigation.
- **`limit` clamped to 200**, `offset` floored at 0 — same guardrails as Feature 4.
- **`_both` closure** keeps filter clauses applied to the page query and the count query in lockstep. The single easiest bug in a paginated endpoint is a `total` that ignores a filter; Feature 4's checklist caught it by testing, this one prevents it structurally.
- **`|` on the search clause** is SQLAlchemy's `OR`. Wrap it exactly as written — Python's `|` binds tighter than comparison, and the parentheses around each `ilike` are what make it parse correctly.

### 3.2 New route

**File:** `apps/business-api/src/business_api/main.py`
**Placement:** immediately after the `customer_360` route (keeps the CRM-adjacent reads together), before the sessions routes.

```python
@app.get("/api/v1/tickets")
def ticket_index(session: DbSession, role: SuperviseurRole, limit: int = 50, offset: int = 0,
                 status: str | None = None, category: str | None = None,
                 priority: str | None = None, customer_id: str | None = None,
                 search: str | None = None) -> dict:
    """Supervision list over the local GLPI ticket mirror.

    GLPI stays the source of truth. This never writes: ticket mutations must go through the
    ticketing-glpi MCP server so GLPI is updated first and the mirror stays consistent.
    """
    return SupervisionRepository(session).ticket_list(
        limit=limit, offset=offset, status=status, category=category,
        priority=priority, customer_id=customer_id, search=search,
    )
```

Route function named `ticket_index`, repository method named `ticket_list` — same distinct-naming discipline as Feature 4. **Verify the callee name against §3.1 before pasting**; three of the four previous patches surfaced exactly one guide-vs-implementation mismatch each.

No path-collision hazard: `/api/v1/tickets` is a new leaf with no sibling parameterised route. No CORS change (proxy). No new imports in `main.py`.

### 3.3 Response shape

```json
{
  "tickets": [
    {
      "ticket_id": "GLPI-10473",
      "status": "in_progress",
      "subject": "No data since Tuesday",
      "category": "network_complaint",
      "priority": "high",
      "customer_id": "9ab2…",
      "customer_name": "Karim Haddad",
      "customer_vip": false,
      "subscription_id": null,
      "created_at": "2026-08-01T09:12:44+00:00",
      "last_synced_at": "2026-08-03T07:55:01+00:00"
    }
  ],
  "total": 87,
  "counts": { "open": 41, "in_progress": 18, "pending": 6, "resolved": 14, "closed": 8 },
  "limit": 50,
  "offset": 0
}
```

`counts` may omit statuses with zero rows — the frontend must default missing keys to `0`, not render blanks.

---

## 4. Findings that drive the design (F1–F18)

### F1 — The mirror is the sanctioned read surface, and it is already reachable
No MCP client, no GLPI credentials, no new service dependency for `business-api`. The alternative — proxying reads through the MCP server — would put GLPI's availability on the critical path of a dashboard page load, and `lookup_tickets` is **per-customer only** (`lookup_tickets(customer_id, ...)`), so it cannot answer "show me all tickets" at all. There is no estate-wide read in the MCP surface. The mirror is not merely the better option; it is the only one.

### F2 — The mirror can be incomplete, and the UI must say so ⚠️
Every mirror write is best-effort:

```python
    except Exception as exc:
        logger.warning("ticket mirror create failed (%s): %s", glpi_ticket_id, exc)
```

A GLPI ticket can exist with **no mirror row** (mirror write failed, or `DATABASE_URL` was unset when it was created, or it was raised directly in GLPI for a customer who never called). The mirror is *"tickets this platform knows about"*, **not** *"all tickets in GLPI"*.

**Design consequence:** the page header states the scope in plain words, and every row exposes `last_synced_at`. A supervisor who cannot see how stale a projection is will treat it as gospel. Never label this view "All tickets".

### F3 — Writing the mirror directly produces edits that silently vanish ☠️
The reconciliation path is `upsert_from_glpi()`, called from `get_ticket_status` and `lookup_tickets`:

```python
            else:
                row.status = _normalize_status(status)
```

GLPI's status is written **over** the mirror row. So a dashboard-side mirror write would:
1. appear to succeed,
2. show the new status,
3. be **overwritten by GLPI's old value** the next time any caller asked about that ticket — possibly days later, with no error anywhere.

An edit that disappears long after the fact is worse than an edit that is refused, because nobody learns the system rejected it. **This is the reason Feature 5 is read-only**, and it is a stronger reason than "rule 2 says so".

### F4 — `customer_360` cannot back this page
It returns `{glpi_id, status, subject}` for **one** customer: no priority, no category, no dates, no pagination, and it is keyed by a customer you must already have chosen. The mock is an estate-wide table. New endpoint required.

### F5 — ✅ The status vocabulary maps **exactly**, for the first time in this series
`_ALLOWED_STATUS` is `open | in_progress | pending | resolved | closed`. `status.ts` contains **all five**: `open` (ring/high/outline), `in_progress` (half/medium/soft), `pending` (ring/medium/outline), `resolved` (disc/low/soft), `closed` (square/inert/flat).

Features 1, 3 and 4 each hit the blank-chip defect where `StatusChip` returns `null` for an unknown key. **Here there is nothing to remap.** The DB `CheckConstraint` guarantees the value is one of the five, so `<StatusChip status={ticket.status} />` is correct as written in the mock.

I still route it through a `ticketStatusKey()` with an identity mapping plus a defensive fallback — not because the constraint can be violated, but because the mock's habit of passing raw backend strings into `StatusChip` is exactly what produced three previous defects, and a named function is where the next person looks. The fallback costs nothing and documents the invariant.

### F6 — ✅ `PriorityMeter` finally has real semantics (unlike Feature 3)
In Feature 3 I **refused** to use `PriorityMeter` because callbacks store `priority_level` as an unconstrained integer and mapping it onto named severities would have invented meaning.

Tickets are different: `priority` is a **named string** from `{low, medium, high, urgent}`, and `PriorityMeter` takes a string level backed by `LEVEL_TONE` (`critical`, `high`, `medium`, `low`, `inert`). The mapping is honest:

| DB `priority` | `PriorityMeter` level |
|---|---|
| `urgent` | `critical` |
| `high` | `high` |
| `medium` | `medium` |
| `low` | `low` |
| `NULL` | **`inert`** |

**`NULL` must map to `inert`, never to `low`.** "Nobody triaged this" and "someone judged this low" are different facts, and `inert` is the token that already means the former. `priority` is nullable in both the model and the check constraint, so nulls are expected, not exceptional.

### F7 — The "Advisor" column has no data behind it anywhere
The mock renders an Advisor avatar per ticket. There is **no assignee column** in `Ticket`, no assignee field in `_row_to_dict`, and no assignee in any MCP tool's return shape. GLPI itself tracks assignees, but nothing in this platform mirrors or exposes them.

**Decision: the column is dropped**, and the freed width goes to Category — which is real, filterable, and currently not shown at all. Flagged in §8.3 with the cost of adding it properly.

### F8 — "Updated" would be a lie; the honest word is "Synced"
The mock's last column is `Updated`. There is **no `updated_at`** on `Ticket` — only `created_at` and `last_synced_at`, and the latter means *"when we last agreed with GLPI"*, which is bumped by any sync even when nothing about the ticket changed.

Labelling `last_synced_at` as "Updated" would tell a supervisor the ticket changed when it did not. **The column is labelled `Synced`**, with `created_at` shown in the ticket cell. Small wording change; it is the difference between a true and a false statement.

### F9 — `StatCard` is unusable here (same as Feature 3)
`StatCard`'s `delta` prop is **non-optional** (`blocks.tsx`), and status counts have no delta — there is no historical series to compare against. Passing a fabricated delta would be inventing data.

**Decision (consistent with Feature 3's stats treatment):** render the five counts inside a single `Card` as `t-metric-m` + `t-micro` columns. As a bonus they become the status filter — clicking a count filters the table — so they earn their space instead of being decoration.

### F10 — ☠️ "New ticket" would text a real customer on WhatsApp
This is the most dangerous control in the entire template. `create_ticket` files in GLPI, mirrors the row, **and then posts to the notification-service to send a `ticket_created` WhatsApp message to the customer**.

An admin idly clicking "New ticket" to see what happens would message a real person. Beyond that, `create_ticket` requires a `customer_id` that the dashboard cannot resolve — there is still **no customer search endpoint** (the same gap that deferred manual booking in Feature 3), only `/customers/{id}/360`.

**Decision: the button is removed, not disabled.** A disabled button invites "why is this greyed out?" and eventually someone enables it. Rationale recorded in §8.2.

### F11 — The mock's footer is a hardcoded lie
`Showing {TICKETS.length} of 205 tickets`, with `Previous`/`Next` buttons wired to nothing. Replaced with real `total` from the endpoint and a working Load-more, following Feature 4's pattern.

### F12 — Category is real, filterable, and currently invisible
Five constrained values, `NOT NULL`, defaulted to `'other'`. It is the most useful filter on the page (network complaints vs billing are different operational queues) and the mock does not surface it at all. It takes the column freed by F7.

### F13 — `glpi_ticket_id` is the identifier, not `id`
`String(40)`, unique, e.g. `GLPI-10473`. The UUID primary key is internal plumbing and **must never be displayed** — it is meaningless to anyone who then goes looking for it in GLPI. The mock's `<Token>{t.id}</Token>` treatment is correct once `id` becomes `ticket_id`.

### F14 — Timezone: same inverse rule as Features 3 and 4
`created_at` and `last_synced_at` are bare UTC ISO instants; there is no business-local string in the payload. So we **must** convert, into the **business** zone.

**Reuse `formatBusinessTime` from `callback-view.ts` (Feature 3) — do not write a third copy.** The zone comes from `getCoverage({ days: 1 }).timezone`, already cached if the operator has visited `/availability`, `/callbacks` or `/calls`. Fallback: render UTC **with a visible caption**, never silently.

### F15 — `customer_id` is nullable
A mirrored ticket may have no customer (mirror write raced, or GLPI-side ticket reconciled without a resolvable customer). Render `Unknown customer`; never `"null null"`, and never call `initials()` with null. Same treatment as Feature 4's anonymous callers.

### F16 — `subject` is nullable and truncated at 255
`mirror_create` does `(subject or "")[:255] or None`. Render `—` with `text-ink-5` for a null subject rather than an empty cell, so the row does not look broken.

### F17 — There is no ticket detail to show
The `description` passed to `create_ticket` goes to **GLPI only** — it is never mirrored. There is no `resolution` column either. A detail drawer would therefore display exactly the fields already in the table row, plus whitespace.

**Decision: no detail view, and no `?ticket=` deep link.** Feature 4 added a deep link because the detail (the transcript) was substantial; here there is nothing behind the click. Adding a drawer would imply depth the data does not have. Flagged in §8.4 alongside the GLPI deep-link alternative, which is genuinely useful.

### F18 — The E2E harness must not touch ticketing (stronger than Feature 4)
Feature 1's harness destroyed `advisor_shifts` with `CREATE TABLE … AS SELECT` + `DROP`. That rule stands, and here it is sharper: **any write through the real ticket path reaches GLPI and can text a customer.**

- Verification is **100% read-only**. Every endpoint in this feature is a `GET`.
- Do **not** call any `ticketing-glpi` MCP tool from a test.
- If fixtures are needed, `INSERT` mirror rows directly into `ticketing.tickets` with an obvious synthetic `glpi_ticket_id` prefix (e.g. `TEST-…`) and `DELETE` them by that key. Direct mirror inserts are safe **for fixtures only** because nothing reconciles a ticket id GLPI has never heard of — but never do this to a real ticket id (F3).

---

## 5. Frontend implementation plan

### 5.1 File manifest

| File | Action |
|---|---|
| `src/lib/api/tickets.server.ts` | **new** — 1 server function, read-only |
| `src/lib/nexus/ticket-view.ts` | **new** — pure helpers |
| `src/lib/nexus/query-keys.ts` | **modified** — append standalone `ticketKeys` |
| `src/lib/nexus/data.ts` | **modified** — remove ticket mocks (guarded, §5.5) |
| `src/routes/tickets.tsx` | **rewritten** |
| `src/routeTree.gen.ts` | **must not change** |
| `nav.ts`, `status.ts`, `primitives.tsx`, `blocks.tsx`, `modal.tsx`, `format.ts` | **untouched** |

Zero new npm dependencies · zero new tokens · zero mutations · no `Modal` (so the `PageSection` `.rise` transform trap does not arise).

### 5.2 `src/lib/api/tickets.server.ts`

> **Copy the middleware composition from the shipped `availability.server.ts`.** `requireRole` is a **factory** — `requireRole("superviseur")`. Feature 2 proved a guide's stated shape can diverge from the implementation; verify against the real file.

```ts
import { createServerFn } from "@tanstack/react-start";
import { z } from "zod";
import { businessApi } from "@/lib/api/business-api";
import { authedMiddleware, requireRole } from "@/lib/api/middleware";

export type TicketRow = {
  ticket_id: string;
  status: string;
  subject: string | null;
  category: string;
  priority: string | null;
  customer_id: string | null;
  customer_name: string | null;
  customer_vip: boolean;
  subscription_id: string | null;
  created_at: string | null;
  last_synced_at: string | null;
};

export type TicketIndex = {
  tickets: TicketRow[];
  total: number;
  counts: Record<string, number>;
  limit: number;
  offset: number;
};

const ListInput = z.object({
  limit: z.number().int().min(1).max(200).default(50),
  offset: z.number().int().min(0).default(0),
  status: z.string().trim().max(20).optional(),
  category: z.string().trim().max(40).optional(),
  priority: z.string().trim().max(10).optional(),
  search: z.string().trim().max(80).optional(),
});

export const listTickets = createServerFn({ method: "GET" })
  .middleware([authedMiddleware, requireRole("superviseur")])
  .inputValidator((data: unknown) => ListInput.parse(data))
  .handler(async ({ data }) =>
    businessApi<TicketIndex>("/api/v1/tickets", {
      method: "GET",
      query: {
        limit: data.limit,
        offset: data.offset,
        ...(data.status ? { status: data.status } : {}),
        ...(data.category ? { category: data.category } : {}),
        ...(data.priority ? { priority: data.priority } : {}),
        ...(data.search ? { search: data.search } : {}),
      },
      role: "superviseur",
    }),
  );
```

Empty filters are **omitted**, never sent as `?status=` — an empty string would filter for the empty status and return nothing (the inverse of the callbacks `status=""` behaviour in Feature 3, and a trap precisely because that one worked the other way).

### 5.3 `src/lib/nexus/ticket-view.ts`

```ts
import { formatBusinessTime } from "@/lib/nexus/callback-view";

/** F5 — identity mapping: the DB CheckConstraint already guarantees these five keys exist
 *  in status.ts. The function exists so the invariant is named, and so an out-of-band value
 *  can never render a blank chip (the defect Features 1, 3 and 4 each hit). */
export function ticketStatusKey(status: string | null): string {
  switch (status) {
    case "open":
    case "in_progress":
    case "pending":
    case "resolved":
    case "closed":
      return status;
    default:
      return "open";
  }
}

/** F6 — named priorities map honestly onto LEVEL_TONE. NULL is `inert`, never `low`:
 *  "not triaged" and "judged low" are different facts. */
export function ticketPriorityLevel(priority: string | null): string {
  switch (priority) {
    case "urgent":
      return "critical";
    case "high":
      return "high";
    case "medium":
      return "medium";
    case "low":
      return "low";
    default:
      return "inert";
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  network_complaint: "Network",
  formal_complaint: "Complaint",
  technical: "Technical",
  billing: "Billing",
  other: "Other",
};

export function categoryLabel(category: string | null): string {
  if (!category) return "Other";
  return CATEGORY_LABELS[category] ?? category;
}

export const STATUS_ORDER = ["open", "in_progress", "pending", "resolved", "closed"] as const;

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  in_progress: "In progress",
  pending: "Pending",
  resolved: "Resolved",
  closed: "Closed",
};

/** F9 — counts omit zero-row statuses; never render a blank. */
export function statusCount(counts: Record<string, number> | undefined, status: string): number {
  return counts?.[status] ?? 0;
}

/** F16 — subject is nullable and truncated at 255 upstream. */
export function ticketSubject(subject: string | null): string {
  return subject?.trim() || "—";
}

/** F15 — tickets can have no customer. */
export function ticketCustomer(name: string | null): string {
  return name?.trim() || "Unknown customer";
}

/** F14 — no local string in this payload; convert into the BUSINESS zone. */
export function ticketTime(iso: string | null, timeZone: string | null): string {
  return formatBusinessTime(iso, timeZone);
}
```

No client-side search helper: filtering is **server-side** (the client holds one page, so a local filter would silently filter only that page — the same reasoning as Feature 4).

### 5.4 `src/lib/nexus/query-keys.ts`

```ts
export const ticketKeys = {
  all: ["tickets"] as const,
  list: (status: string, category: string, priority: string, search: string, limit: number) =>
    ["tickets", "list", status, category, priority, search, limit] as const,
};
```

Standalone export, mirroring `availabilityKeys` / `callbackKeys` / `callKeys`. `limit` is in the key because Load-more grows it.

### 5.5 `src/lib/nexus/data.ts` — guarded mock removal

Targets: `TICKETS`, `TICKET_STATS`, `TicketRow`.

> **Grep before deleting.** `TicketRow` is a plausible import in `customers.tsx` or `overview.tsx`, and our new `TicketRow` type lives in `tickets.server.ts` — **name collision is likely**.
>
> ```bash
> grep -rn "TICKETS\|TICKET_STATS\|TicketRow" src/
> ```
>
> Remove only symbols whose sole importer was `tickets.tsx`. If another mock-driven page still uses them, leave them until that page is wired. A broken build in an untouched route is self-inflicted.

### 5.6 `src/routes/tickets.tsx` (rewritten)

Structure preserved: two `PageSection`s (stats, then table), `TableShell` with `toolbar` / `head` / `footer`, `Token` + subject in the ticket cell, `PriorityMeter`, `StatusChip`, right-aligned final column. A reviewer should recognise it instantly.

```tsx
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { TicketX } from "lucide-react";
import {
  Button,
  Card,
  EmptyState,
  PriorityMeter,
  SearchInput,
  Segmented,
  StatusChip,
  TableShell,
  Td,
  Th,
  Token,
} from "@/components/nexus/primitives";
import { PageSection } from "@/components/nexus/app-topbar";
import { TableErrorRow, TableSkeleton } from "@/components/nexus/states";
import { getCoverage } from "@/lib/api/availability.server";
import { listTickets } from "@/lib/api/tickets.server";
import {
  STATUS_LABELS,
  STATUS_ORDER,
  categoryLabel,
  statusCount,
  ticketCustomer,
  ticketPriorityLevel,
  ticketStatusKey,
  ticketSubject,
  ticketTime,
} from "@/lib/nexus/ticket-view";
import { ticketKeys } from "@/lib/nexus/query-keys";
import { formatInteger } from "@/lib/nexus/format";

const CATEGORIES = [
  { id: "", label: "All" },
  { id: "network_complaint", label: "Network" },
  { id: "formal_complaint", label: "Complaint" },
  { id: "technical", label: "Technical" },
  { id: "billing", label: "Billing" },
  { id: "other", label: "Other" },
];

export const Route = createFileRoute("/tickets")({
  head: () => ({
    meta: [
      { title: "Ticket Management — Nexus" },
      {
        name: "description",
        content: "Support tickets mirrored from GLPI, with status, priority and sync freshness.",
      },
      { property: "og:title", content: "Ticket Management — Nexus" },
      { property: "og:description", content: "Open, in-progress, resolved and closed tickets." },
    ],
  }),
  component: TicketsPage,
});

function TicketsPage() {
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [limit, setLimit] = useState(50);

  const ticketsQuery = useQuery({
    queryKey: ticketKeys.list(status, category, "", search, limit),
    queryFn: () =>
      listTickets({
        data: {
          limit,
          offset: 0,
          status: status || undefined,
          category: category || undefined,
          search: search || undefined,
        },
      }),
  });

  // F14 — business timezone; shared cache with /availability, /callbacks and /calls.
  const coverageQuery = useQuery({
    queryKey: ["availability", "coverage", 1],
    queryFn: () => getCoverage({ data: { days: 1 } }),
  });
  const timeZone = coverageQuery.data?.timezone ?? null;

  const rows = ticketsQuery.data?.tickets ?? [];
  const total = ticketsQuery.data?.total ?? 0;
  const counts = ticketsQuery.data?.counts;

  return (
    <>
      {/* ---------- Status counts (F9: not StatCard — no delta exists) ---------- */}
      <PageSection>
        <Card>
          <div className="grid grid-cols-2 gap-sp-6 md:grid-cols-5">
            {STATUS_ORDER.map((key) => {
              const active = status === key;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setStatus(active ? "" : key)}
                  className="text-left"
                  aria-pressed={active}
                >
                  <span className="t-micro block text-ink-5">{STATUS_LABELS[key]}</span>
                  <span
                    className={active ? "t-metric-m block text-ink-1" : "t-metric-m block text-ink-3"}
                  >
                    {formatInteger(statusCount(counts, key))}
                  </span>
                </button>
              );
            })}
          </div>
          {/* F2 — never let this read as "all GLPI tickets". */}
          <p className="t-caption mt-sp-6 text-ink-5">
            Mirrored from GLPI. Tickets raised outside this platform appear once a caller asks
            about them.
            {!timeZone && !coverageQuery.isPending
              ? " Times shown in UTC — the business timezone could not be loaded."
              : null}
          </p>
        </Card>
      </PageSection>

      {/* ---------- Table ---------- */}
      <PageSection>
        <TableShell
          toolbar={
            <>
              <SearchInput
                placeholder="Search subject or ID"
                className="w-[260px]"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <Segmented items={CATEGORIES} active={category} onSelect={setCategory} />
            </>
          }
          head={
            <tr>
              <Th>Ticket</Th>
              <Th>Customer</Th>
              <Th>Category</Th>
              <Th>Priority</Th>
              <Th>Status</Th>
              {/* F8 — "Synced", not "Updated": last_synced_at is when we last agreed with GLPI. */}
              <Th align="right">Synced</Th>
            </tr>
          }
          footer={
            <>
              <span className="t-caption text-ink-4">
                Showing {rows.length} of {formatInteger(total)} tickets
              </span>
              {rows.length < total ? (
                <Button size="sm" onClick={() => setLimit((n) => Math.min(n + 50, 200))}>
                  Load more
                </Button>
              ) : null}
            </>
          }
        >
          {ticketsQuery.isPending ? (
            <TableSkeleton rows={6} cols={6} />
          ) : ticketsQuery.isError ? (
            <TableErrorRow
              colSpan={6}
              message={ticketsQuery.error}
              onRetry={() => ticketsQuery.refetch()}
            />
          ) : rows.length === 0 ? (
            <tr>
              <Td colSpan={6}>
                <EmptyState
                  icon={TicketX}
                  title="No tickets found"
                  description="No mirrored ticket matches this filter."
                />
              </Td>
            </tr>
          ) : (
            rows.map((t) => (
              <tr
                key={t.ticket_id}
                className="transition-colors duration-[120ms] hover:bg-surface-3"
              >
                <Td>
                  <span className="flex items-center gap-sp-5">
                    {/* F13 — the GLPI id, never the internal UUID. */}
                    <Token>{t.ticket_id}</Token>
                    <span className="t-ui truncate text-ink-1">{ticketSubject(t.subject)}</span>
                  </span>
                </Td>
                <Td>
                  <span className="flex items-center gap-sp-4">
                    <span className="truncate">{ticketCustomer(t.customer_name)}</span>
                    {t.customer_vip ? <Token strong>VIP</Token> : null}
                  </span>
                </Td>
                <Td>
                  <Token mono={false}>{categoryLabel(t.category)}</Token>
                </Td>
                <Td>
                  {/* F6 — named priorities map honestly; NULL renders as inert. */}
                  <PriorityMeter priority={ticketPriorityLevel(t.priority)} />
                </Td>
                <Td>
                  <StatusChip status={ticketStatusKey(t.status)} />
                </Td>
                <Td align="right">
                  <span className="t-mono text-ink-3">
                    {ticketTime(t.last_synced_at, timeZone)}
                  </span>
                </Td>
              </tr>
            ))
          )}
        </TableShell>
      </PageSection>
    </>
  );
}
```

**Call-site adaptations to verify against the shipped components** (call-site only — never edit primitives):

- **`SearchInput`** in the template takes `{ placeholder, className }`. Feature 4 raised the same question. **Check whether Feature 0/1 already extended it to forward `value`/`onChange`;** if not, wrap a local `<input>` with identical classes rather than modifying the component.
- **`Td colSpan`** — confirm `Td` forwards `colSpan`. If it does not, use a plain `<td colSpan={6} className="…">` matching `Td`'s classes, exactly as the shipped `advisors.tsx` does for its empty row. Mirror that file.
- **`TableErrorRow`** takes `{ colSpan, message, onRetry }`; `errorMessage` handles plain strings since the Feature 1 fix.
- **`Segmented`** — `{ id, label }` + `onSelect`, `type="button"` since Feature 1.
- **`EmptyState`** icon usage must mirror the exact call shape in shipped `advisors.tsx`.
- **`formatInteger`** already exists in `format.ts`. Do not write a number formatter.
- The coverage query key is written inline above; **use the exported `availabilityKeys.coverage(1)`** instead, so the cache is genuinely shared with `/availability`, `/callbacks` and `/calls`. Import it from `query-keys.ts` — an inline literal that merely *looks* the same is a silent cache miss if the exported builder ever changes.

---

## 6. Design-system compliance

| Rule | How it is met |
|---|---|
| No new colours | Only `text-ink-*` / `bg-surface-3`; `PriorityMeter` and `StatusChip` supply all tone |
| No new type styles | `t-ui`, `t-mono`, `t-micro`, `t-caption`, `t-metric-m` |
| No new spacing | `gap-sp-4/5/6`, `mt-sp-6` |
| No new components | `Button`, `Card`, `EmptyState`, `PriorityMeter`, `SearchInput`, `Segmented`, `StatusChip`, `TableShell`, `Td`, `Th`, `Token` |
| No new status keys | F5 — identity mapping; all five already canonical |
| No new priority levels | F6 — maps onto existing `LEVEL_TONE` entries |
| Achromatic | grep proves no `#hex` / `rgb(` |

---

## 7. Validation checklist

### 7.1 Static

- [ ] `bun --bun tsc --noEmit` → exit 0.
- [ ] `bun --bun run lint` → **exactly the 36-problem baseline**. No new problems.
- [ ] `bun --bun run build` → exit 0 (pre-existing `inputValidator` deprecation notices only).
- [ ] `git diff --stat src/routeTree.gen.ts` → **empty**.
- [ ] Backend diff → **only** `repositories.py` (+1 method) and `main.py` (+1 route). **Import blocks unchanged in both.**
- [ ] `git status` backend → the 2 pre-existing agent-worker files still the only other changes.
- [ ] `package.json` / `bun.lock` unchanged.
- [ ] `grep -rn "rgb(\|#[0-9a-fA-F]\{3,6\}"` on the two new frontend files → no hits.
- [ ] `grep -n "getDay(\|toLocaleString(\|getHours("` on the new files → no hits.
- [ ] `status.ts`, `primitives.tsx`, `blocks.tsx`, `modal.tsx`, `format.ts`, `nav.ts` → untouched.
- [ ] **No import of any MCP client, GLPI URL or GLPI token** anywhere in `business-api` or the dashboard.
- [ ] `ruff check apps/business-api` → clean at line-length 110.

### 7.2 Pure helpers

- [ ] `ticketStatusKey` for all five vocabulary values returns a key **present in `status.ts`** (assert against the real table).
- [ ] `ticketStatusKey("nonsense")` → `"open"`, and `StatusChip` renders **non-null** for it.
- [ ] `ticketPriorityLevel` → `urgent→critical`, `high→high`, `medium→medium`, `low→low`.
- [ ] **`ticketPriorityLevel(null)` → `"inert"`, NOT `"low"`** (F6).
- [ ] `categoryLabel` for all five values; unknown passes through unchanged.
- [ ] `statusCount(undefined, "open")` → `0`; `statusCount({}, "closed")` → `0`.
- [ ] `ticketSubject(null)` and `ticketSubject("   ")` → `"—"`.
- [ ] `ticketCustomer(null)` → `"Unknown customer"`.
- [ ] `ticketTime(null, tz)` → `"—"`; `ticketTime("garbage", tz)` → `"—"`.
- [ ] `ticketTime` identical under `TZ=America/New_York` and `TZ=Africa/Tunis`.

### 7.3 Backend contract (read-only)

- [ ] `X-Role: conseiller` → **403**; `superviseur` → 200; `administrateur` → 200.
- [ ] `?limit=999` → clamped to **200**; `?limit=0` / `-5` → clamped to 1.
- [ ] `?offset` beyond `total` → `tickets: []`, `total` unchanged.
- [ ] **`total` respects every filter** — `?status=open` → `total` equals the open count, not the table count. (The `_both` closure exists for this; verify it anyway.)
- [ ] **`counts` ignores the status filter** — identical `counts` with and without `?status=open`.
- [ ] `counts` omits zero-row statuses → UI still renders `0` (F9).
- [ ] `?category=billing` and `?priority=urgent` each narrow correctly.
- [ ] `?search=` matches **both** subject substrings **and** `glpi_ticket_id` substrings, case-insensitively.
- [ ] `?customer_id=<garbage>` → treated as no filter, no 500.
- [ ] Ordering: `created_at DESC`.
- [ ] A ticket with `customer_id IS NULL` → `customer_name: null`, no crash.
- [ ] A ticket with `priority IS NULL` → `priority: null` in JSON.
- [ ] A ticket with `subject IS NULL` → `subject: null`.
- [ ] **The internal UUID never appears in any response** (F13) — grep the JSON.
- [ ] Response key names match `_row_to_dict` exactly, plus `customer_name` / `customer_vip`.

### 7.4 Live E2E (browser, full Docker stack)

- [ ] Unauthenticated `/tickets` → `/login`; after login → renders.
- [ ] Sidebar entry and existing `PAGE_META` subtitle unchanged.
- [ ] Five status counts render; a zero-count status shows `0`, not blank.
- [ ] Clicking a status count filters the table; clicking the **same** one again clears the filter.
- [ ] While filtered, the counts **do not change** (they stay whole-table).
- [ ] Category `Segmented` through all six values.
- [ ] Search by subject fragment, then by GLPI id fragment — both narrow.
- [ ] Combined status + category + search returns a consistent `total`.
- [ ] `Load more` grows the page; button disappears at `rows.length === total`.
- [ ] **No blank chip anywhere** — every row shows a status chip (F5).
- [ ] A `NULL`-priority ticket renders the **inert** meter, visibly distinct from `low` (F6).
- [ ] A `NULL`-subject ticket shows `—`, row not broken.
- [ ] A `NULL`-customer ticket shows `Unknown customer`.
- [ ] Empty result → `EmptyState` inside the table, not a collapsed shell.
- [ ] The GLPI-scope caption is visible (F2).
- [ ] Timezone: OS at `America/New_York` → Synced column identical to `Africa/Tunis`.
- [ ] Break coverage only → UTC caption appears; times still render.
- [ ] `docker stop docker-compose-business-api-1` → `TableErrorRow` with Retry; restart → recovery without reload.
- [ ] **Zero direct browser requests to `:8108`.**
- [ ] **Zero requests to `:8202`** from the browser or from `business-api` (F1/F3 — grep the logs).
- [ ] `/calls`, `/callbacks`, `/availability`, `/advisors` still render (shared coverage cache is read-only here).
- [ ] Any other page importing the removed mocks still builds (§5.5 grep).

> **Harness rule (F18): this checklist is 100% read-only. Do not call any `ticketing-glpi` MCP tool — writes reach real GLPI and `create_ticket` sends the customer a WhatsApp message.** Fixtures, if needed: `INSERT` mirror rows with a `TEST-` prefixed `glpi_ticket_id`, `DELETE` by that key. Never `CREATE TABLE … AS SELECT` + `DROP` (the Feature 1 incident that destroyed `advisor_shifts`).

---

## 8. Ambiguities & decisions needing your confirmation

### 8.1 Ticket mutation — the real design question
Admins will want to resolve, close, reprioritise and reassign from this page. Doing that correctly means **GLPI first, mirror second**, which is what every MCP tool already guarantees. Three options:

1. **Read-only (this cookbook).** Safe today. Admins change tickets in GLPI itself; the change flows back into the mirror on the next reconciliation.
2. **`business-api` gains an MCP client** and proxies `update_ticket` / `resolve_ticket` / `close_ticket` to `:8202`. Correct ordering preserved, one new dependency (`business-api` → MCP), and `business-api` gains its first outbound service call. **My recommendation if you want mutation** — it reuses the proven write path rather than duplicating it.
3. **`business-api` talks to GLPI directly** with its own credentials. **Rejected:** it duplicates `glpi_client` logic, doubles the credential surface, and creates a second write path that can drift from the MCP one. Two writers to one external system with different code is how mirrors rot.

Option 2 is arguably rule-3(c) access-creation, but it adds a service dependency, so I want explicit approval. **Under no circumstances do we write `ticketing.tickets` from the dashboard** (F3).

### 8.2 "New ticket" removed, not disabled
Removed for two independent reasons: `create_ticket` **WhatsApps the customer**, and there is still **no customer search endpoint** to resolve a `customer_id` (the same gap that deferred manual callback booking in Feature 3). Confirm removal is right. If you want admin-side ticket creation later it needs: a customer search endpoint, option 2 above, and an explicit decision about whether the admin-created ticket should notify the customer at all — that last one is a product question, not a technical one.

### 8.3 The Advisor column is gone
No assignee exists in the mirror or in any MCP tool return shape (F7). GLPI tracks assignees internally. Surfacing them would need: an `assignee` column on `ticketing.tickets`, `_row_to_dict` extended, and `upsert_from_glpi` reading the assignee out of the GLPI payload — i.e. **changes to the MCP server and the shared schema**, well outside "expose existing data". Confirm you are content without it, or schedule it as its own backend task.

### 8.4 No detail view — but a GLPI deep link is available
`description` and `resolution` live only in GLPI (F17), so a drawer would show nothing new. The genuinely useful alternative is an **"Open in GLPI"** link per row: `GLPI_BASE_URL` is already an env var on the MCP server, and the ticket id is right there. It needs a **dashboard-side** env var (`GLPI_WEB_URL`) plus knowledge of your GLPI URL scheme for tickets. Confirm you want it and tell me the URL pattern.

### 8.5 Mirror completeness — an operational question, not a code one
The mirror only contains what the platform touched or reconciled (F2). If GLPI holds substantially more tickets than `ticketing.tickets`, this page understates the estate. Worth running once:

```sql
SELECT status, count(*) FROM ticketing.tickets GROUP BY status;
```

and comparing to GLPI's own count. If the gap is large, a periodic full reconciliation job (GLPI → mirror) would be the fix — a backend job, not a dashboard feature, and it would make this page complete as a side effect. Tell me what the numbers look like and I will scope it.

### 8.6 `subscription_id` is returned but not displayed
It is in the sanctioned row shape so I kept it in the payload, but there is no subscription lookup endpoint to turn it into anything human-readable (`crm.subscriptions` is only reachable nested inside `customer_360`). It costs nothing to carry and will be useful when Customers is wired. Say if you would rather drop it.

### 8.7 Category filter uses shortened labels
`network_complaint` → "Network", `formal_complaint` → "Complaint". The raw values are unwieldy in a `Segmented` control, and "Complaint" vs "Network" reads better than "Formal complaint" vs "Network complaint". If your operators use the GLPI wording verbatim, say so and I will use the full labels.

---

## 9. Summary of the diff

**Backend (additive only, 2 files):**
- `repositories.py` — `+1` method `ticket_list`, **zero new imports**, no existing line changed.
- `main.py` — `+1` route `GET /api/v1/tickets` (`superviseur`).

**Frontend (`Frontend/admin_dashboard/` only):**
- **new** `src/lib/api/tickets.server.ts`, `src/lib/nexus/ticket-view.ts`
- **modified** `src/lib/nexus/query-keys.ts` (append `ticketKeys`), `src/lib/nexus/data.ts` (guarded removal)
- **rewritten** `src/routes/tickets.tsx`
- **unchanged** `routeTree.gen.ts`, `nav.ts`, `status.ts`, `primitives.tsx`, `blocks.tsx`, `modal.tsx`, `format.ts`

**Zero** new npm dependencies · **zero** new tokens · **zero** new status keys · **zero** mutations · **zero** MCP calls · **zero** GLPI credentials · **zero** CORS changes · **zero** navigation changes.

---

## 10. Next feature

**Knowledge / RAG (`/knowledge`).** Expect a structurally similar problem with a different answer: ingestion and semantic search live behind the **`ai-knowledge-rag` MCP server on :8201** and the **knowledge-service on :8102**, and `business-api` exposes neither. The decisive question will be whether documents have a Postgres projection the way tickets do — if they do, this same mirror-read pattern applies; if they do not, `/knowledge` cannot be made read-only-safe the same way, because document **ingestion is inherently a write**. Reads still outstanding for it: the knowledge-service surface, the `ai-knowledge-rag` tool list, and any `persistence.models` document table.
