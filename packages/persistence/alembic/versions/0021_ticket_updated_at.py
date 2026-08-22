"""Horodatage de derniere modification d'un ticket.

`ticketing.tickets` has carried `created_at` and `last_synced_at` since 0005 and nothing in
between. That is a real gap, not a cosmetic one:

  - `last_synced_at` is bumped by every reconciliation pass, including one that changed nothing
    (`upsert_from_glpi` writes it on every lookup). It answers "when did we last talk to GLPI
    about this row", which is operational metadata, not a fact about the ticket.
  - So there was no column answering "when did this request last actually change" — and the
    customer portal's Requests screen renders exactly that field in two places (the detail panel
    and Activity's request body). `me_reads.requests()` never returned it, the portal's
    `RequestItem` type declared it `string | null`, and both screens therefore printed an em dash
    forever.

`updated_at` closes it. Backfilled to `created_at` so an existing ticket reads as "last changed
when it was opened", which is true of every row that has never been touched since.

Safety: additive and NOT NULL only because it is filled in the same statement that adds it. The
SQLAlchemy model carries `onupdate=now()`, so every ORM mutation path already in the codebase
(`mirror_update`, `mirror_set_status`, `mirror_resolve`, `upsert_from_glpi`) stamps it without a
single call-site change. Nothing reads the column unless it asks for it, so every existing SELECT,
INSERT and CheckConstraint is untouched.

Revision ID: 0021_ticket_updated_at
Revises: 0020_ticket_admin_note
"""
from alembic import op
import sqlalchemy as sa

revision = "0021_ticket_updated_at"
down_revision = "0020_ticket_admin_note"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="ticketing",
    )
    # A ticket nobody has touched was last changed when it was opened. Without this the whole
    # existing table would claim it changed at migration time, which is the one answer we know
    # to be wrong.
    op.execute("UPDATE ticketing.tickets SET updated_at = created_at")

    # The portal's Requests list orders by created_at; Activity merges tickets with conversations
    # and callbacks on recency. An index on updated_at keeps the "recently changed" read cheap as
    # the mirror grows.
    op.create_index(
        "ix_tickets_customer_updated",
        "tickets",
        ["customer_id", "updated_at"],
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_index("ix_tickets_customer_updated", table_name="tickets", schema="ticketing")
    op.drop_column("tickets", "updated_at", schema="ticketing")
