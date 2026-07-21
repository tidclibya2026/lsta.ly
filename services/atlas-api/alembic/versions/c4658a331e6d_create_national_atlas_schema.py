"""create national atlas schema

Revision ID: c4658a331e6d
Revises:
Create Date: 2026-07-14 14:56:59.234365
"""

from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4658a331e6d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS atlas")
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "data_sources",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_file", sa.String(length=500), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_sources")),
        sa.UniqueConstraint("sha256", name="uq_data_sources_sha256"),
        schema="atlas",
    )
    op.create_table(
        "municipalities",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_municipalities")),
        sa.UniqueConstraint("code", name=op.f("uq_municipalities_code")),
        schema="atlas",
    )
    op.create_table(
        "site_categories",
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_site_categories_code")),
        schema="atlas",
    )
    op.create_table(
        "audit_log",
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
        schema="audit",
    )
    op.create_table(
        "sites",
        sa.Column("national_id", sa.String(length=100), nullable=False),
        sa.Column("name_ar", sa.String(length=500), nullable=False),
        sa.Column("name_en", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("municipality_id", sa.Uuid(), nullable=True),
        sa.Column("data_source_id", sa.Uuid(), nullable=True),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('draft', 'imported', 'pending_review', 'needs_correction', 'gis_review', 'data_review', 'approved', 'rejected', 'archived')",
            name=op.f("ck_sites_sites_verification_status"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["atlas.site_categories.id"], name=op.f("fk_sites_category_id_site_categories")
        ),
        sa.ForeignKeyConstraint(
            ["data_source_id"], ["atlas.data_sources.id"], name=op.f("fk_sites_data_source_id_data_sources")
        ),
        sa.ForeignKeyConstraint(
            ["municipality_id"], ["atlas.municipalities.id"], name=op.f("fk_sites_municipality_id_municipalities")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sites")),
        sa.UniqueConstraint("national_id", name=op.f("uq_sites_national_id")),
        schema="atlas",
    )
    op.create_index(
        "ix_sites_name_ar_trgm",
        "sites",
        ["name_ar"],
        unique=False,
        schema="atlas",
        postgresql_using="gin",
        postgresql_ops={"name_ar": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_sites_name_en_trgm",
        "sites",
        ["name_en"],
        unique=False,
        schema="atlas",
        postgresql_using="gin",
        postgresql_ops={"name_en": "gin_trgm_ops"},
    )
    op.create_index(
        op.f("ix_sites_verification_status"), "sites", ["verification_status"], unique=False, schema="atlas"
    )
    op.create_table(
        "import_batches",
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["data_source_id"], ["atlas.data_sources.id"], name=op.f("fk_import_batches_data_source_id_data_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_batches")),
        schema="staging",
    )
    op.create_table(
        "media_assets",
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(length=50), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"], ["atlas.sites.id"], name=op.f("fk_media_assets_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
        schema="atlas",
    )
    op.create_table(
        "publication_records",
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("publication_status", sa.String(length=40), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "publication_status IN ('internal', 'approved_internal', 'approved_public', 'published_public', 'sent_to_visit_libya', 'withdrawn')",
            name=op.f("ck_publication_records_publication_records_status"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["atlas.sites.id"], name=op.f("fk_publication_records_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publication_records")),
        schema="atlas",
    )
    op.create_index(
        op.f("ix_publication_records_publication_status"),
        "publication_records",
        ["publication_status"],
        unique=False,
        schema="atlas",
    )
    op.create_table(
        "site_geometries",
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("geometry_type", sa.String(length=40), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["site_id"], ["atlas.sites.id"], name=op.f("fk_site_geometries_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_site_geometries")),
        schema="atlas",
    )
    op.create_index(
        "ix_site_geometries_geometry_gist",
        "site_geometries",
        ["geometry"],
        unique=False,
        schema="atlas",
        postgresql_using="gist",
    )
    op.create_table(
        "verification_records",
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("verification_status", sa.String(length=40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('draft', 'imported', 'pending_review', 'needs_correction', 'gis_review', 'data_review', 'approved', 'rejected', 'archived')",
            name=op.f("ck_verification_records_verification_records_status"),
        ),
        sa.ForeignKeyConstraint(
            ["site_id"], ["atlas.sites.id"], name=op.f("fk_verification_records_site_id_sites"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_verification_records")),
        schema="atlas",
    )
    op.create_index(
        op.f("ix_verification_records_verification_status"),
        "verification_records",
        ["verification_status"],
        unique=False,
        schema="atlas",
    )
    op.create_table(
        "import_features",
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("source_feature_id", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=500), nullable=True),
        sa.Column("geometry_type", sa.String(length=40), nullable=False),
        sa.Column(
            "geometry",
            geoalchemy2.types.Geometry(
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing_name", sa.Boolean(), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('pending_review', 'accepted', 'rejected', 'needs_correction')",
            name=op.f("ck_import_features_import_features_review_status"),
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["staging.import_batches.id"],
            name=op.f("fk_import_features_batch_id_import_batches"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_features")),
        schema="staging",
    )
    op.create_index("ix_import_features_batch_id", "import_features", ["batch_id"], unique=False, schema="staging")
    op.create_index(
        "ix_import_features_geometry_gist",
        "import_features",
        ["geometry"],
        unique=False,
        schema="staging",
        postgresql_using="gist",
    )
    op.create_index(
        "ix_import_features_source_feature_id", "import_features", ["source_feature_id"], unique=False, schema="staging"
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index("ix_import_features_source_feature_id", table_name="import_features", schema="staging")
    op.drop_index(
        "ix_import_features_geometry_gist", table_name="import_features", schema="staging", postgresql_using="gist"
    )
    op.drop_index("ix_import_features_batch_id", table_name="import_features", schema="staging")
    op.drop_table("import_features", schema="staging")
    op.drop_index(
        op.f("ix_verification_records_verification_status"), table_name="verification_records", schema="atlas"
    )
    op.drop_table("verification_records", schema="atlas")
    op.drop_index(
        "ix_site_geometries_geometry_gist", table_name="site_geometries", schema="atlas", postgresql_using="gist"
    )
    op.drop_table("site_geometries", schema="atlas")
    op.drop_index(op.f("ix_publication_records_publication_status"), table_name="publication_records", schema="atlas")
    op.drop_table("publication_records", schema="atlas")
    op.drop_table("media_assets", schema="atlas")
    op.drop_table("import_batches", schema="staging")
    op.drop_index(op.f("ix_sites_verification_status"), table_name="sites", schema="atlas")
    op.drop_index(
        "ix_sites_name_en_trgm",
        table_name="sites",
        schema="atlas",
        postgresql_using="gin",
        postgresql_ops={"name_en": "gin_trgm_ops"},
    )
    op.drop_index(
        "ix_sites_name_ar_trgm",
        table_name="sites",
        schema="atlas",
        postgresql_using="gin",
        postgresql_ops={"name_ar": "gin_trgm_ops"},
    )
    op.drop_table("sites", schema="atlas")
    op.drop_table("audit_log", schema="audit")
    op.drop_table("site_categories", schema="atlas")
    op.drop_table("municipalities", schema="atlas")
    op.drop_table("data_sources", schema="atlas")
    # ### end Alembic commands ###
