"""Note d'administrateur sur un ticket (mise a jour manuelle du statut).

Lets an administrator record WHY a ticket moved state, in a place the voice agent can read back
to the customer on the next call.

Why the note lives in the mirror rather than only in GLPI: the agent reads tickets through
`get_ticket_status` / `lookup_tickets`, and both return the mirror row (see
ticketing-glpi/adapters/mirror._row_to_dict). GLPI's own `solution` field is never read back by
`LiveGlpiClient.get()`, so a note written only to GLPI would be invisible to the agent. The note
is therefore written to BOTH: GLPI stays the source of truth for the ticket, and the mirror
carries the text the agent speaks.

Safety: all three columns are NULLABLE and additive. Every existing INSERT, SELECT and the
CheckConstraints on status/category/priority are untouched, so the mirror keeps working exactly
as before for rows that never receive a note.

Revision ID: 0020_ticket_admin_note
Revises: 0019_agent_activity_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_ticket_admin_note"
down_revision = "0019_agent_activity_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tickets",
        sa.Column("admin_note", sa.Text(), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        # The acting admin's email, as recorded on the audit entry for the same change.
        sa.Column("note_author", sa.String(255), nullable=True),
        schema="ticketing",
    )
    op.add_column(
        "tickets",
        sa.Column("note_updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="ticketing",
    )
    # A note without a timestamp cannot be aged or ordered, and a timestamp without a note is
    # meaningless. Enforcing the pair keeps "is there a note?" a single, unambiguous question.
    op.create_check_constraint(
        "admin_note_timestamped",
        "tickets",
        "(admin_note IS NULL) = (note_updated_at IS NULL)",
        schema="ticketing",
    )


def downgrade() -> None:
    op.drop_constraint(
        "admin_note_timestamped", "tickets", schema="ticketing", type_="check"
    )
    op.drop_column("tickets", "note_updated_at", schema="ticketing")
    op.drop_column("tickets", "note_author", schema="ticketing")
    op.drop_column("tickets", "admin_note", schema="ticketing")
