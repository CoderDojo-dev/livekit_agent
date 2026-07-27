"""Description de panne + rattachement canonique (problemes #2 et #3).

Revision ID: 0015_outage_description_area_code
Revises: 0014_geo_reference
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_outage_description_area_code"
down_revision = "0014_geo_reference"
branch_labels = None
depends_on = None

CAUSES = (
    "'fiber_cut','power_failure','equipment_failure','planned_maintenance',"
    "'congestion','weather','third_party_damage'"
)


def upgrade() -> None:
    op.add_column("outages", sa.Column("area_code", sa.String(40)), schema="oss")
    op.add_column("outages", sa.Column("cause", sa.String(60)), schema="oss")
    op.add_column("outages", sa.Column("description_fr", sa.Text()), schema="oss")
    op.add_column("outages", sa.Column("description_ar", sa.Text()), schema="oss")
    op.add_column("outages", sa.Column("description_en", sa.Text()), schema="oss")

    op.create_foreign_key(
        "fk_outages_area_code", "outages", "geo_areas",
        ["area_code"], ["area_code"],
        source_schema="oss", referent_schema="reference",
    )
    op.create_index("ix_outages_area_code", "outages", ["area_code"], schema="oss")
    op.create_check_constraint(
        "cause", "outages",
        "cause IS NULL OR cause IN (" + CAUSES + ")",
        schema="oss",
    )


def downgrade() -> None:
    op.drop_constraint("ck_outages_cause", "outages", schema="oss", type_="check")
    op.drop_index("ix_outages_area_code", "outages", schema="oss")
    op.drop_constraint("fk_outages_area_code", "outages", schema="oss",
                       type_="foreignkey")
    for column in ("description_en", "description_ar", "description_fr",
                   "cause", "area_code"):
        op.drop_column("outages", column, schema="oss")
