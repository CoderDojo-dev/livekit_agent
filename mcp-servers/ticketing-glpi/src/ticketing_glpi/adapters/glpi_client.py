"""GLPI ticket client: full CRUD over the GLPI REST API, with an in-memory mock twin.

GLPI is the source of truth for tickets; the Postgres mirror (mirror.py) is a durable, queryable
local projection of it. Both clients expose the SAME interface so the MCP tools never branch on
mode:

    create(customer_id, subject, description, category, priority, requester_glpi_id) -> Ticket
    get(ticket_id)                     -> Ticket | None
    update(ticket_id, **fields)        -> Ticket | None
    resolve(ticket_id, resolution)     -> Ticket | None
    close(ticket_id)                   -> Ticket | None
    delete(ticket_id)                  -> bool
    list_for(requester_glpi_id)        -> list[Ticket]

The live client speaks the documented GLPI REST API (apirest.php): initSession returns a
Session-Token used with the App-Token on every call; tickets are created/read/updated at
/Ticket, searched at /search/Ticket with numeric field ids (12=status, 4=requester,
2=id, 1=name/title), and the numeric status maps to our vocabulary.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# GLPI numeric status codes -> our ticketing.tickets vocabulary.
# GLPI: 1 new, 2 assigned(processing), 3 planned, 4 waiting(pending), 5 solved, 6 closed.
_GLPI_STATUS_TO_LOCAL = {1: "open", 2: "in_progress", 3: "in_progress", 4: "pending",
                         5: "resolved", 6: "closed"}
_LOCAL_TO_GLPI_STATUS = {"open": 1, "in_progress": 2, "pending": 4, "resolved": 5, "closed": 6}

# Our priority vocabulary -> GLPI priority (1 very low .. 6 very high; we use the middle band).
_LOCAL_TO_GLPI_PRIORITY = {"low": 2, "medium": 3, "high": 4, "urgent": 5}

# GLPI search-engine field ids for itemtype Ticket (stable across GLPI 9.5/10.x).
_FIELD_ID = 2
_FIELD_STATUS = 12
_FIELD_REQUESTER = 4


def local_status(glpi_status: int | str | None) -> str:
    """Map a GLPI numeric status to our vocabulary (unknown -> 'open')."""
    try:
        return _GLPI_STATUS_TO_LOCAL.get(int(glpi_status), "open")
    except (TypeError, ValueError):
        return "open"


@dataclass
class Ticket:
    """A GLPI ticket in our terms. ``status`` uses the local vocabulary."""

    ticket_id: str                 # our external id, e.g. "GLPI-42"
    customer_id: str               # our customer UUID (may be "" when read raw from GLPI)
    subject: str
    description: str
    status: str                    # open | in_progress | pending | resolved | closed
    resolution: str | None = None
    category: str = "other"
    priority: str | None = None


def _numeric(ticket_id: str) -> str:
    """The numeric GLPI id from our external 'GLPI-<n>' form."""
    return ticket_id.replace("GLPI-", "").strip()


class MockGlpiClient:
    """In-memory GLPI twin for local dev, CI and offline verification. Same interface as live."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0

    def create(self, customer_id: str, subject: str, description: str,
               category: str = "other", priority: str | None = None,
               requester_glpi_id: int | None = None) -> Ticket:
        self._counter += 1
        ticket_id = f"GLPI-{self._counter:05d}"
        ticket = Ticket(ticket_id, customer_id, subject, description, status="open",
                        category=category, priority=priority)
        self._tickets[ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def update(self, ticket_id: str, subject: str | None = None,
               description: str | None = None, priority: str | None = None,
               status: str | None = None) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        if subject is not None:
            ticket.subject = subject
        if description is not None:
            ticket.description = description
        if priority is not None:
            ticket.priority = priority
        if status is not None:
            ticket.status = status
        return ticket

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "resolved"
        ticket.resolution = resolution
        return ticket

    def close(self, ticket_id: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "closed"
        return ticket

    def delete(self, ticket_id: str) -> bool:
        return self._tickets.pop(ticket_id, None) is not None

    def list_for(self, requester_glpi_id: int | str) -> list[Ticket]:
        # The mock keys on our customer_id; the live client keys on the GLPI requester id.
        return [t for t in self._tickets.values() if t.customer_id == str(requester_glpi_id)]


class LiveGlpiClient:
    """Real GLPI REST client. Interface-compatible with MockGlpiClient.

    Trace context is injected on every outbound call so a ticket operation stays on the same
    distributed trace as the voice turn that triggered it.
    """

    def __init__(self, base_url: str, app_token: str, user_token: str) -> None:
        self._base = base_url.rstrip("/")
        self._app = app_token
        self._user = user_token

    # -- session / headers -------------------------------------------------------------------
    def _trace_headers(self, headers: dict) -> dict:
        try:
            from observability_kit.telemetry import inject_trace_context
            return inject_trace_context(headers)
        except Exception:
            return headers

    def _open_session(self, client: httpx.Client) -> dict:
        resp = client.get("/initSession", headers=self._trace_headers({
            "App-Token": self._app,
            "Authorization": f"user_token {self._user}",
        }))
        resp.raise_for_status()
        return {"App-Token": self._app, "Session-Token": resp.json()["session_token"]}

    def _kill_session(self, client: httpx.Client, headers: dict) -> None:
        try:
            client.get("/killSession", headers=headers)
        except Exception:
            pass

    # -- CRUD --------------------------------------------------------------------------------
    def create(self, customer_id: str, subject: str, description: str,
               category: str = "other", priority: str | None = None,
               requester_glpi_id: int | None = None) -> Ticket:
        payload: dict = {"name": subject, "content": description, "status": 1}
        if priority in _LOCAL_TO_GLPI_PRIORITY:
            payload["priority"] = _LOCAL_TO_GLPI_PRIORITY[priority]
        if requester_glpi_id:
            payload["_users_id_requester"] = int(requester_glpi_id)
        with httpx.Client(base_url=self._base, timeout=8.0) as client:
            headers = self._open_session(client)
            try:
                resp = client.post("/Ticket", headers=self._trace_headers(headers),
                                   json={"input": payload})
                resp.raise_for_status()
                tid = str(resp.json().get("id"))
            finally:
                self._kill_session(client, headers)
        return Ticket(f"GLPI-{tid}", customer_id, subject, description, status="open",
                      category=category, priority=priority)

    def get(self, ticket_id: str) -> Ticket | None:
        with httpx.Client(base_url=self._base, timeout=8.0) as client:
            headers = self._open_session(client)
            try:
                resp = client.get(f"/Ticket/{_numeric(ticket_id)}",
                                  headers=self._trace_headers(headers))
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
            finally:
                self._kill_session(client, headers)
        # Map the requester back to a caller identity when GLPI returns one.
        requester = data.get("users_id_recipient") or data.get("_users_id_requester") or ""
        return Ticket(
            ticket_id=ticket_id,
            customer_id=str(requester) if requester else "",
            subject=data.get("name", ""),
            description=data.get("content", ""),
            status=local_status(data.get("status", 1)),
        )

    def _put(self, ticket_id: str, fields: dict) -> bool:
        with httpx.Client(base_url=self._base, timeout=8.0) as client:
            headers = self._open_session(client)
            try:
                resp = client.put(f"/Ticket/{_numeric(ticket_id)}",
                                  headers=self._trace_headers(headers),
                                  json={"input": fields})
                if resp.status_code == 404:
                    return False
                resp.raise_for_status()
                return True
            finally:
                self._kill_session(client, headers)

    def update(self, ticket_id: str, subject: str | None = None,
               description: str | None = None, priority: str | None = None,
               status: str | None = None) -> Ticket | None:
        fields: dict = {}
        if subject is not None:
            fields["name"] = subject
        if description is not None:
            fields["content"] = description
        if priority in _LOCAL_TO_GLPI_PRIORITY:
            fields["priority"] = _LOCAL_TO_GLPI_PRIORITY[priority]
        if status in _LOCAL_TO_GLPI_STATUS:
            fields["status"] = _LOCAL_TO_GLPI_STATUS[status]
        if not fields:
            return self.get(ticket_id)
        if not self._put(ticket_id, fields):
            return None
        return self.get(ticket_id)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        if not self._put(ticket_id, {"status": 5, "solution": resolution}):
            return None
        return Ticket(ticket_id, customer_id="", subject="", description="",
                      status="resolved", resolution=resolution)

    def close(self, ticket_id: str) -> Ticket | None:
        if not self._put(ticket_id, {"status": 6}):
            return None
        return Ticket(ticket_id, customer_id="", subject="", description="", status="closed")

    def delete(self, ticket_id: str) -> bool:
        with httpx.Client(base_url=self._base, timeout=8.0) as client:
            headers = self._open_session(client)
            try:
                # force_purge deletes rather than moving the ticket to the trash bin.
                resp = client.delete(f"/Ticket/{_numeric(ticket_id)}",
                                     headers=self._trace_headers(headers),
                                     params={"force_purge": "true"})
                if resp.status_code == 404:
                    return False
                resp.raise_for_status()
                return True
            finally:
                self._kill_session(client, headers)

    def list_for(self, requester_glpi_id: int | str) -> list[Ticket]:
        """Search tickets whose requester is ``requester_glpi_id`` (GLPI search field 4)."""
        if not requester_glpi_id:
            return []
        params = {
            "criteria[0][field]": str(_FIELD_REQUESTER),
            "criteria[0][searchtype]": "equals",
            "criteria[0][value]": str(requester_glpi_id),
            "forcedisplay[0]": str(_FIELD_ID),
            "forcedisplay[1]": str(_FIELD_STATUS),
            "range": "0-200",
        }
        with httpx.Client(base_url=self._base, timeout=8.0) as client:
            headers = self._open_session(client)
            try:
                resp = client.get("/search/Ticket", headers=self._trace_headers(headers),
                                  params=params)
                if resp.status_code in (404, 400):
                    return []
                resp.raise_for_status()
                body = resp.json()
            finally:
                self._kill_session(client, headers)
        rows = body.get("data", []) if isinstance(body, dict) else []
        tickets: list[Ticket] = []
        for row in rows:
            # Search rows are keyed by numeric field id (strings). 2=id, 1=title, 12=status.
            gid = row.get(str(_FIELD_ID)) or row.get(_FIELD_ID)
            if gid is None:
                continue
            tickets.append(Ticket(
                ticket_id=f"GLPI-{gid}",
                customer_id=str(requester_glpi_id),
                subject=str(row.get("1", "") or row.get(1, "")),
                description="",
                status=local_status(row.get(str(_FIELD_STATUS)) or row.get(_FIELD_STATUS)),
            ))
        return tickets


class GlpiConfigError(RuntimeError):
    """CONNECTOR_MODE=live was requested but the GLPI connection is not configured.

    Raised instead of silently degrading to the in-memory mock: a ticketing system with no real
    GLPI behind it would accept tickets that vanish on restart while looking healthy. Fail loud.
    """


def get_glpi_client():
    """Return the GLPI client for the current mode.

    CONNECTOR_MODE=live (production/staging and any real setup): a LiveGlpiClient bound to a real
    GLPI REST endpoint. If the credentials are missing, this RAISES rather than falling back to
    the mock - there must always be a real system behind live mode.

    CONNECTOR_MODE=mock (local dev / CI only): an in-memory GLPI twin with no external dependency.
    Never reachable unless mock is explicitly selected.
    """
    mode = os.getenv("CONNECTOR_MODE", "mock").lower()
    if mode == "live":
        base = os.getenv("GLPI_BASE_URL")
        app = os.getenv("GLPI_APP_TOKEN")
        user = os.getenv("GLPI_USER_TOKEN")
        missing = [name for name, value in
                   (("GLPI_BASE_URL", base), ("GLPI_APP_TOKEN", app), ("GLPI_USER_TOKEN", user))
                   if not value]
        if missing:
            raise GlpiConfigError(
                "CONNECTOR_MODE=live but these GLPI settings are missing: "
                + ", ".join(missing)
                + ". Set them (or use CONNECTOR_MODE=mock for local dev). Refusing to fall back "
                "to the in-memory mock, which would silently drop real tickets."
            )
        logger.info("ticketing: using LiveGlpiClient at %s", base)
        return LiveGlpiClient(base, app, user)
    logger.warning("ticketing: CONNECTOR_MODE=mock - in-memory GLPI twin (local dev only)")
    return MockGlpiClient()
