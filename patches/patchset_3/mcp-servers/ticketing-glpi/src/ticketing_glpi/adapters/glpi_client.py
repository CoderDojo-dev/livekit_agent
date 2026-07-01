"""Mock GLPI client (in-memory ticket store). A real GLPI REST adapter replaces this without
changing the tools. Tickets become Postgres/GLPI-backed in the persistence phase.
"""
from __future__ import annotations

import os

import httpx

from dataclasses import dataclass


@dataclass
class Ticket:
    """A GLPI ticket."""

    ticket_id: str
    customer_id: str
    subject: str
    description: str
    status: str            # "new" | "resolved"
    resolution: str | None = None


class MockGlpiClient:
    """In-memory GLPI ticket lifecycle."""

    def __init__(self) -> None:
        self._tickets: dict[str, Ticket] = {}
        self._counter = 0

    def create(self, customer_id: str, subject: str, description: str) -> Ticket:
        self._counter += 1
        ticket_id = f"GLPI-{self._counter:05d}"
        ticket = Ticket(ticket_id, customer_id, subject, description, status="new")
        self._tickets[ticket_id] = ticket
        return ticket

    def get(self, ticket_id: str) -> Ticket | None:
        return self._tickets.get(ticket_id)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket.status = "resolved"
        ticket.resolution = resolution
        return ticket

    def list_for(self, customer_id: str) -> list[Ticket]:
        return [t for t in self._tickets.values() if t.customer_id == customer_id]


class LiveGlpiClient:
    """Real GLPI REST client (report #4). Same interface as MockGlpiClient so the tools are unchanged.

    Uses the GLPI REST API: initSession (App-Token + user_token) -> session token, then Ticket CRUD.
    `list_for` is left as a no-op search (returns []) until the customer↔ticket search is bound.
    """

    def __init__(self, base_url: str, app_token: str, user_token: str) -> None:
        self._base = base_url
        self._app = app_token
        self._user = user_token

    def _headers(self, client: "httpx.Client") -> dict:
        r = client.get("/initSession", headers={
            "App-Token": self._app, "Authorization": f"user_token {self._user}",
        })
        r.raise_for_status()
        return {"App-Token": self._app, "Session-Token": r.json()["session_token"]}

    def create(self, customer_id: str, subject: str, description: str) -> Ticket:
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.post("/Ticket", headers=h, json={"input": {"name": subject, "content": description}})
            r.raise_for_status()
            tid = str(r.json().get("id"))
            return Ticket(f"GLPI-{tid}", customer_id, subject, description, status="new")

    def get(self, ticket_id: str) -> Ticket | None:
        numeric = ticket_id.replace("GLPI-", "")
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.get(f"/Ticket/{numeric}", headers=h)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            d = r.json()
            status = "resolved" if int(d.get("status", 1)) >= 5 else "new"
            return Ticket(ticket_id, customer_id="", subject=d.get("name", ""),
                          description=d.get("content", ""), status=status)

    def resolve(self, ticket_id: str, resolution: str) -> Ticket | None:
        numeric = ticket_id.replace("GLPI-", "")
        with httpx.Client(base_url=self._base, timeout=8.0) as c:
            h = self._headers(c)
            r = c.put(f"/Ticket/{numeric}", headers=h,
                      json={"input": {"status": 5, "solution": resolution}})  # 5 = solved
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return Ticket(ticket_id, customer_id="", subject="", description="", status="resolved",
                          resolution=resolution)

    def list_for(self, customer_id: str) -> list[Ticket]:
        return []  # GLPI search binding TODO; the Postgres mirror answers lookups meanwhile


def get_glpi_client():
    """Return the live GLPI client when CONNECTOR_MODE=live and GLPI creds are set; else the mock."""
    if os.getenv("CONNECTOR_MODE", "mock").lower() == "live":
        base = os.getenv("GLPI_BASE_URL")
        app = os.getenv("GLPI_APP_TOKEN")
        user = os.getenv("GLPI_USER_TOKEN")
        if base and app and user:
            return LiveGlpiClient(base, app, user)
    return MockGlpiClient()