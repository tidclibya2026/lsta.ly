"""controlled final merge execution engine

Revision ID: d3f40a91b672
Revises: fc80934e3eff
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "d3f40a91b672"
down_revision = "fc80934e3eff"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("merge_execution_batches",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("execution_code", sa.String(160), nullable=False),
        sa.Column("merge_batch_id", sa.Uuid(), sa.ForeignKey("staging.merge_batches.id"), nullable=False),
        sa.Column("requested_proposal_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("eligible_proposal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_proposal_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_proposal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_proposal_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("execution_mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(40), nullable=False), sa.Column("requested_by_role", sa.String(100), nullable=False), sa.Column("requested_by_reference", sa.String(150)),
        sa.Column("dry_run_report", postgresql.JSONB(), nullable=False, server_default="{}"), sa.Column("validation_summary", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("execution_mode IN ('dry_run','controlled_execution','rollback_preview')", name="ck_merge_execution_batches_mode"),
        sa.CheckConstraint("status IN ('draft','validated','blocked','approved_for_execution','running','completed','completed_with_errors','failed','cancelled','rolled_back')", name="ck_merge_execution_batches_status"),
        sa.UniqueConstraint("execution_code", name="uq_merge_execution_batches_code"), schema="staging")
    op.create_index("ix_merge_execution_batches_merge_batch", "merge_execution_batches", ["merge_batch_id", "status"], schema="staging")
    op.create_table("merge_execution_items",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("execution_batch_id", sa.Uuid(), sa.ForeignKey("staging.merge_execution_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), sa.ForeignKey("staging.merge_proposals.id"), nullable=False), sa.Column("operation_type", sa.String(40), nullable=False),
        sa.Column("target_site_id", sa.Uuid(), sa.ForeignKey("atlas.sites.id")), sa.Column("target_national_id", sa.String(100)),
        sa.Column("pre_merge_snapshot", postgresql.JSONB()), sa.Column("proposed_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("field_merge_plan", postgresql.JSONB(), nullable=False), sa.Column("validation_results", postgresql.JSONB(), nullable=False),
        sa.Column("execution_status", sa.String(30), nullable=False), sa.Column("error_code", sa.String(100)), sa.Column("error_message", sa.Text()), sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("operation_type IN ('create_national_site','update_existing_site','keep_separate','no_operation')", name="ck_merge_execution_items_operation"),
        sa.CheckConstraint("execution_status IN ('pending','eligible','blocked','executing','completed','failed','skipped','rolled_back')", name="ck_merge_execution_items_status"),
        sa.UniqueConstraint("execution_batch_id", "proposal_id", name="uq_merge_execution_item_proposal"), schema="staging")
    op.create_index("ix_merge_execution_items_proposal_status", "merge_execution_items", ["proposal_id", "execution_status"], schema="staging")
    op.create_table("merge_execution_events", sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("execution_batch_id", sa.Uuid(), sa.ForeignKey("staging.merge_execution_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_item_id", sa.Uuid(), sa.ForeignKey("staging.merge_execution_items.id", ondelete="CASCADE")), sa.Column("proposal_id", sa.Uuid(), sa.ForeignKey("staging.merge_proposals.id")),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("actor_role", sa.String(100), nullable=False), sa.Column("actor_reference", sa.String(150)),
        sa.Column("event_payload", postgresql.JSONB(), nullable=False, server_default="{}"), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="audit")
    op.create_index("ix_merge_execution_events_batch_time", "merge_execution_events", ["execution_batch_id", "occurred_at"], schema="audit")


def downgrade() -> None:
    op.drop_index("ix_merge_execution_events_batch_time", table_name="merge_execution_events", schema="audit")
    op.drop_table("merge_execution_events", schema="audit")
    op.drop_index("ix_merge_execution_items_proposal_status", table_name="merge_execution_items", schema="staging")
    op.drop_table("merge_execution_items", schema="staging")
    op.drop_index("ix_merge_execution_batches_merge_batch", table_name="merge_execution_batches", schema="staging")
    op.drop_table("merge_execution_batches", schema="staging")
