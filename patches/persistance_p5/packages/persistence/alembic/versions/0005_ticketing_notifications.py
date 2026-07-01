"""ticketing mirror + notification log: ticketing.tickets, billing.notifications.

Revision ID: 0005_ticketing_notif
Revises: 0004_domain_writes
Create Date: 2026-06-29
"""
from alembic import op

from persistence.base import Base
from persistence.models.billing import Notification
from persistence.models.ticketing import Ticket

revision = "0005_ticketing_notif"
down_revision = "0004_domain_writes"
branch_labels = None
depends_on = None

_NEW = [Ticket.__table__, Notification.__table__]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_NEW)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ticketing.tickets CASCADE")
    op.execute("DROP TABLE IF EXISTS billing.notifications CASCADE")
