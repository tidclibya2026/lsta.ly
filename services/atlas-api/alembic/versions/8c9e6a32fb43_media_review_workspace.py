"""media review workspace

Revision ID: 8c9e6a32fb43
Revises: 7b8d5f21ea32
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8c9e6a32fb43"
down_revision: Union[str, None] = "7b8d5f21ea32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_review_items",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("feature_id", sa.String(255), nullable=False),
        sa.Column("site_id", sa.Uuid()),
        sa.Column("site_name", sa.String(500)),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("normalized_url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(300), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(60), nullable=False),
        sa.Column("review_status", sa.String(30), nullable=False, server_default="pending_review"),
        sa.Column("rights_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("rights_owner", sa.String(500)),
        sa.Column("rights_evidence", sa.Text()),
        sa.Column("intended_use", sa.String(40), nullable=False, server_default="internal_review"),
        sa.Column("reviewer_role", sa.String(100)),
        sa.Column("reviewer_notes", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("download_status", sa.String(30), nullable=False, server_default="not_requested"),
        sa.Column("local_media_url", sa.Text()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "review_status IN ('pending_review','approved','rejected','needs_information')",
            name="media_review_review_status",
        ),
        sa.CheckConstraint(
            "rights_status IN ('unknown','pending_review','approved_internal','approved_public','restricted')",
            name="media_review_rights_status",
        ),
        sa.CheckConstraint(
            "download_status IN ('not_requested','queued','downloaded','failed','skipped')",
            name="media_review_download_status",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["atlas.sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_id", "original_url", name="uq_media_review_feature_url"),
        schema="metadata",
    )
    for name, column in (
        ("ix_media_review_status", "review_status"),
        ("ix_media_review_rights", "rights_status"),
        ("ix_media_review_download", "download_status"),
        ("ix_media_review_domain", "domain"),
        ("ix_media_review_feature", "feature_id"),
    ):
        op.create_index(name, "media_review_items", [column], schema="metadata")


def downgrade() -> None:
    op.drop_table("media_review_items", schema="metadata")
