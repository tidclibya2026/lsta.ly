"""National Search and Discovery Engine.

Revision ID: 9d1f7a44ce10
Revises: 8c9e6a32fb43
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "9d1f7a44ce10"
down_revision = "8c9e6a32fb43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def timestamps() -> list[sa.Column]:
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS search")
    op.create_table("saved_queries", sa.Column("id", UUID, primary_key=True), sa.Column("user_id", UUID), sa.Column("query_name", sa.String(300), nullable=False), sa.Column("query_text", sa.Text(), nullable=False, server_default=""), sa.Column("normalized_query", sa.Text(), nullable=False, server_default=""), sa.Column("filters", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("spatial_filter", JSONB), sa.Column("sort_by", sa.String(60)), sa.Column("sort_order", sa.String(10)), sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), *timestamps(), schema="search")
    op.create_index("ix_saved_queries_normalized_query", "saved_queries", ["normalized_query"], schema="search")
    op.create_index("ix_saved_queries_filters_gin", "saved_queries", ["filters"], unique=False, postgresql_using="gin", schema="search")
    op.create_index("ix_saved_queries_spatial_filter_gin", "saved_queries", ["spatial_filter"], unique=False, postgresql_using="gin", schema="search")
    op.create_table("search_logs", sa.Column("id", UUID, primary_key=True), sa.Column("user_id", UUID), sa.Column("role", sa.String(80)), sa.Column("query_text", sa.Text(), nullable=False, server_default=""), sa.Column("normalized_query", sa.Text(), nullable=False, server_default=""), sa.Column("source_scope", sa.String(40), nullable=False), sa.Column("filters", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("query_time_ms", sa.Numeric(12, 3), nullable=False, server_default="0"), sa.Column("selected_result_type", sa.String(80)), sa.Column("selected_result_id", sa.Text()), sa.Column("no_results", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), schema="search")
    for name, cols in [("ix_search_logs_created_at", ["created_at"]), ("ix_search_logs_no_results", ["no_results"]), ("ix_search_logs_role", ["role"])]: op.create_index(name, "search_logs", cols, schema="search")
    op.create_table("query_statistics", sa.Column("id", UUID, primary_key=True), sa.Column("normalized_query", sa.Text(), nullable=False, unique=True), sa.Column("total_searches", sa.Integer(), nullable=False, server_default="0"), sa.Column("successful_searches", sa.Integer(), nullable=False, server_default="0"), sa.Column("no_result_searches", sa.Integer(), nullable=False, server_default="0"), sa.Column("average_result_count", sa.Numeric(12, 2), nullable=False, server_default="0"), sa.Column("average_query_time_ms", sa.Numeric(12, 3), nullable=False, server_default="0"), sa.Column("last_searched_at", sa.DateTime(timezone=True)), *timestamps(), schema="search")
    op.create_table("search_suggestions", sa.Column("id", UUID, primary_key=True), sa.Column("suggestion_text", sa.Text(), nullable=False), sa.Column("normalized_text", sa.Text(), nullable=False), sa.Column("suggestion_type", sa.String(40), nullable=False), sa.Column("source_reference", sa.Text()), sa.Column("popularity_score", sa.Numeric(8, 2), nullable=False, server_default="0"), sa.Column("relevance_score", sa.Numeric(8, 2), nullable=False, server_default="0"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), *timestamps(), sa.UniqueConstraint("normalized_text", "suggestion_type", "source_reference"), schema="search")
    op.create_index("ix_search_suggestions_popularity", "search_suggestions", ["popularity_score"], schema="search"); op.create_index("ix_search_suggestions_relevance", "search_suggestions", ["relevance_score"], schema="search")
    op.create_table("duplicate_candidates", sa.Column("id", UUID, primary_key=True), sa.Column("source_entity_type", sa.String(40), nullable=False), sa.Column("source_entity_id", sa.Text(), nullable=False), sa.Column("target_entity_type", sa.String(40), nullable=False), sa.Column("target_entity_id", sa.Text(), nullable=False), sa.Column("name_similarity", sa.Numeric(5, 2), nullable=False), sa.Column("spatial_distance_meters", sa.Numeric()), sa.Column("description_similarity", sa.Numeric(5, 2)), sa.Column("category_match", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("municipality_match", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending_review"), sa.Column("reviewer_id", UUID), sa.Column("reviewer_notes", sa.Text()), sa.Column("reviewed_at", sa.DateTime(timezone=True)), *timestamps(), sa.CheckConstraint("status IN ('pending_review','confirmed_duplicate','not_duplicate','merged','ignored')", name="duplicate_candidate_status"), sa.UniqueConstraint("source_entity_type", "source_entity_id", "target_entity_type", "target_entity_id"), schema="search")
    op.create_index("ix_duplicate_confidence", "duplicate_candidates", ["confidence_score"], schema="search"); op.create_index("ix_duplicate_status", "duplicate_candidates", ["status"], schema="search")
    op.create_table("similar_site_cache", sa.Column("id", UUID, primary_key=True), sa.Column("source_site_id", UUID, sa.ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False), sa.Column("target_site_id", UUID, sa.ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False), sa.Column("similarity_score", sa.Numeric(5, 2), nullable=False), sa.Column("similarity_breakdown", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("calculated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("calculation_version", sa.String(40), nullable=False), sa.UniqueConstraint("source_site_id", "target_site_id", "calculation_version"), schema="search")
    op.create_index("ix_similar_source", "similar_site_cache", ["source_site_id"], schema="search"); op.create_index("ix_similar_target", "similar_site_cache", ["target_site_id"], schema="search")
    op.create_table("search_index_status", sa.Column("id", UUID, primary_key=True), sa.Column("entity_type", sa.String(40), nullable=False), sa.Column("entity_id", sa.Text(), nullable=False), sa.Column("indexed_at", sa.DateTime(timezone=True)), sa.Column("index_version", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("error_message", sa.Text()), *timestamps(), sa.CheckConstraint("status IN ('pending','indexed','failed','stale')", name="search_index_status_value"), sa.UniqueConstraint("entity_type", "entity_id", "index_version"), schema="search")


def downgrade() -> None:
    for table in ["search_index_status", "similar_site_cache", "duplicate_candidates", "search_suggestions", "query_statistics", "search_logs", "saved_queries"]: op.drop_table(table, schema="search")
    op.execute("DROP SCHEMA IF EXISTS search")
