"""add merge review workspace

Revision ID: fc80934e3eff
Revises: a41c8e73d902
Create Date: 2026-07-16 12:53:48.952640
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fc80934e3eff"
down_revision: Union[str, None] = "a41c8e73d902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "merge_batches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_code",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "entity_type",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "excel_file_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "excel_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "kml_file_name",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "kml_sha256",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "excel_record_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "kml_record_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "raw_candidate_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "proposal_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "engine_version",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "matching_parameters",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "created_by",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "batch_code",
            name="uq_merge_batches_batch_code",
        ),
        sa.CheckConstraint(
            "status IN ('draft','ready_for_review','under_review','completed','archived','failed')",
            name="merge_batch_status",
        ),
        schema="staging",
    )

    op.create_table(
        "merge_proposals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "excel_record_id",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "kml_record_id",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column(
            "excel_name",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "kml_name",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "confidence_score",
            sa.Numeric(5, 2),
            nullable=False,
        ),
        sa.Column(
            "name_similarity",
            sa.Numeric(5, 2),
            nullable=False,
        ),
        sa.Column(
            "distance_meters",
            sa.Numeric(12, 2),
            nullable=True,
        ),
        sa.Column(
            "candidate_class",
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            "conflict_severity",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column(
            "conflict_fields",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "excel_snapshot",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "kml_snapshot",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "proposed_site",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "field_sources",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "review_status",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'pending_review'"),
        ),
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column(
            "assigned_role",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["staging.merge_batches.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "batch_id",
            "excel_record_id",
            "kml_record_id",
            name="uq_merge_proposal_pair",
        ),
        sa.CheckConstraint(
            "review_status IN ('pending_review','approved_merge','rejected_match','needs_field_verification','create_from_excel','create_from_kml','keep_separate','duplicate_excel','duplicate_kml','deferred')",
            name="merge_proposal_review_status",
        ),
        sa.CheckConstraint(
            "candidate_class IN ('ready_merge','needs_review','possible_match')",
            name="merge_proposal_candidate_class",
        ),
        sa.CheckConstraint(
            "conflict_severity IN ('none','medium','high')",
            name="merge_proposal_conflict_severity",
        ),
        schema="staging",
    )

    op.create_table(
        "merge_decisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "proposal_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "review_stage",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'merge_review'"),
        ),
        sa.Column(
            "reviewer_role",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "reviewer_reference",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column(
            "decision_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "reviewer_notes",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "decision_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["staging.merge_proposals.id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "decision IN ('approved_merge','rejected_match','needs_field_verification','create_from_excel','create_from_kml','keep_separate','duplicate_excel','duplicate_kml','deferred')",
            name="merge_decision_value",
        ),
        schema="staging",
    )

    op.create_index(
        "ix_merge_batches_entity_status",
        "merge_batches",
        ["entity_type", "status"],
        schema="staging",
    )

    op.create_index(
        "ix_merge_proposals_batch_status",
        "merge_proposals",
        ["batch_id", "review_status"],
        schema="staging",
    )

    op.create_index(
        "ix_merge_proposals_candidate_class",
        "merge_proposals",
        ["candidate_class"],
        schema="staging",
    )

    op.create_index(
        "ix_merge_proposals_conflict_severity",
        "merge_proposals",
        ["conflict_severity"],
        schema="staging",
    )

    op.create_index(
        "ix_merge_proposals_conflict_fields_gin",
        "merge_proposals",
        ["conflict_fields"],
        unique=False,
        postgresql_using="gin",
        schema="staging",
    )

    op.create_index(
        "ix_merge_decisions_proposal",
        "merge_decisions",
        ["proposal_id", "decided_at"],
        schema="staging",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_merge_decisions_proposal",
        table_name="merge_decisions",
        schema="staging",
    )

    op.drop_index(
        "ix_merge_proposals_conflict_fields_gin",
        table_name="merge_proposals",
        schema="staging",
    )

    op.drop_index(
        "ix_merge_proposals_conflict_severity",
        table_name="merge_proposals",
        schema="staging",
    )

    op.drop_index(
        "ix_merge_proposals_candidate_class",
        table_name="merge_proposals",
        schema="staging",
    )

    op.drop_index(
        "ix_merge_proposals_batch_status",
        table_name="merge_proposals",
        schema="staging",
    )

    op.drop_index(
        "ix_merge_batches_entity_status",
        table_name="merge_batches",
        schema="staging",
    )

    op.drop_table(
        "merge_decisions",
        schema="staging",
    )

    op.drop_table(
        "merge_proposals",
        schema="staging",
    )

    op.drop_table(
        "merge_batches",
        schema="staging",
    )
