"""Referentiel canonique des zones (problemes #1 et #3).

Revision ID: 0014_geo_reference
Revises: 0013_callback_lifecycle
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0014_geo_reference"
down_revision = "0013_callback_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Recherche par similarite cote base. Necessite un role autorise ;
    # sinon, faire executer cette ligne par un administrateur au prealable.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "geo_areas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("area_code", sa.String(40), nullable=False, unique=True),
        sa.Column("name_fr", sa.String(120), nullable=False),
        sa.Column("name_ar", sa.String(120)),
        sa.Column("name_en", sa.String(120)),
        sa.Column("area_type", sa.String(20), nullable=False),
        sa.Column("parent_code", sa.String(40)),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint(
            "area_type IN ('governorate','delegation','locality')",
            name="ck_geo_areas_area_type",
        ),
        sa.ForeignKeyConstraint(
            ["parent_code"], ["reference.geo_areas.area_code"],
            name="fk_geo_areas_parent",
        ),
        schema="reference",
    )
    op.create_index("ix_geo_areas_parent_code", "geo_areas", ["parent_code"],
                    schema="reference")

    op.create_table(
        "geo_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("area_code", sa.String(40), nullable=False),
        sa.Column("alias", sa.String(160), nullable=False),
        sa.Column("normalized", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["area_code"], ["reference.geo_areas.area_code"],
            name="fk_geo_aliases_area",
        ),
        sa.UniqueConstraint("normalized", name="uq_geo_alias_normalized"),
        schema="reference",
    )
    op.create_index("ix_geo_aliases_area_code", "geo_aliases", ["area_code"],
                    schema="reference")
    # Index trigramme : c'est lui qui rend similarity() rapide.
    op.create_index(
        "ix_geo_aliases_normalized_trgm", "geo_aliases", ["normalized"],
        schema="reference", postgresql_using="gin",
        postgresql_ops={"normalized": "gin_trgm_ops"},
    )


def downgrade() -> None:
    op.drop_table("geo_aliases", schema="reference")
    op.drop_table("geo_areas", schema="reference")
