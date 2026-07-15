"""Government Executive Intelligence Dashboard.

Revision ID: a41c8e73d902
Revises: 9d1f7a44ce10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "a41c8e73d902"
down_revision = "9d1f7a44ce10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
UUID = postgresql.UUID(as_uuid=True); JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS executive")
    op.create_table("dashboard_snapshots",sa.Column("id",UUID,primary_key=True),sa.Column("snapshot_date",sa.Date(),nullable=False),sa.Column("snapshot_type",sa.String(20),nullable=False),sa.Column("metrics",JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("generated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("generated_by",sa.String(120)),sa.Column("source_version",sa.String(100)),sa.CheckConstraint("snapshot_type IN ('daily','weekly','monthly','manual')",name="dashboard_snapshot_type"),sa.UniqueConstraint("snapshot_date","snapshot_type"),schema="executive")
    op.create_index("ix_dashboard_snapshot_date","dashboard_snapshots",["snapshot_date"],schema="executive");op.create_index("ix_dashboard_metrics_gin","dashboard_snapshots",["metrics"],postgresql_using="gin",schema="executive")
    op.create_table("alerts",sa.Column("id",UUID,primary_key=True),sa.Column("alert_code",sa.String(120),nullable=False),sa.Column("alert_type",sa.String(80),nullable=False),sa.Column("severity",sa.String(20),nullable=False),sa.Column("title_ar",sa.String(500),nullable=False),sa.Column("title_en",sa.String(500)),sa.Column("description_ar",sa.Text(),nullable=False),sa.Column("description_en",sa.Text()),sa.Column("source_entity_type",sa.String(80)),sa.Column("source_entity_id",sa.Text()),sa.Column("metric_name",sa.String(120)),sa.Column("metric_value",sa.Numeric()),sa.Column("threshold_value",sa.Numeric()),sa.Column("status",sa.String(30),nullable=False,server_default="open"),sa.Column("assigned_role",sa.String(80)),sa.Column("acknowledged_by",sa.String(120)),sa.Column("acknowledged_at",sa.DateTime(timezone=True)),sa.Column("resolved_by",sa.String(120)),sa.Column("resolved_at",sa.DateTime(timezone=True)),sa.Column("resolution_notes",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("severity IN ('info','warning','high','critical')",name="executive_alert_severity"),sa.CheckConstraint("status IN ('open','acknowledged','in_progress','resolved','dismissed')",name="executive_alert_status"),schema="executive")
    for name,col in [("ix_executive_alert_status","status"),("ix_executive_alert_severity","severity"),("ix_executive_alert_type","alert_type")]:op.create_index(name,"alerts",[col],schema="executive")
    op.create_table("kpi_definitions",sa.Column("id",UUID,primary_key=True),sa.Column("kpi_code",sa.String(120),nullable=False,unique=True),sa.Column("name_ar",sa.String(500),nullable=False),sa.Column("name_en",sa.String(500)),sa.Column("description_ar",sa.Text(),nullable=False),sa.Column("category",sa.String(80),nullable=False),sa.Column("calculation_method",sa.Text(),nullable=False),sa.Column("unit",sa.String(40),nullable=False),sa.Column("target_value",sa.Numeric()),sa.Column("warning_threshold",sa.Numeric()),sa.Column("critical_threshold",sa.Numeric()),sa.Column("direction",sa.String(30),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("display_order",sa.Integer(),nullable=False,server_default="0"),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("direction IN ('higher_is_better','lower_is_better','target_range')",name="kpi_direction"),schema="executive")
    op.create_index("ix_kpi_code","kpi_definitions",["kpi_code"],schema="executive")
    op.create_table("kpi_values",sa.Column("id",UUID,primary_key=True),sa.Column("kpi_id",UUID,sa.ForeignKey("executive.kpi_definitions.id",ondelete="CASCADE"),nullable=False),sa.Column("value",sa.Numeric(),nullable=False),sa.Column("previous_value",sa.Numeric()),sa.Column("change_value",sa.Numeric()),sa.Column("change_percentage",sa.Numeric()),sa.Column("evaluation_status",sa.String(20),nullable=False),sa.Column("measured_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("dimensions",JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("source_reference",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("evaluation_status IN ('good','warning','critical','unavailable')",name="kpi_evaluation_status"),schema="executive")
    op.create_index("ix_kpi_measured_at","kpi_values",["measured_at"],schema="executive");op.create_index("ix_kpi_evaluation","kpi_values",["evaluation_status"],schema="executive");op.create_index("ix_kpi_dimensions_gin","kpi_values",["dimensions"],postgresql_using="gin",schema="executive")
    op.create_table("service_health",sa.Column("id",UUID,primary_key=True),sa.Column("service_code",sa.String(100),nullable=False),sa.Column("service_name",sa.String(300),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("response_time_ms",sa.Numeric(12,3)),sa.Column("details",JSONB,nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("checked_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.CheckConstraint("status IN ('healthy','degraded','unavailable','unknown')",name="service_health_status"),schema="executive")
    op.create_index("ix_service_health_code","service_health",["service_code"],schema="executive");op.create_index("ix_service_health_checked","service_health",["checked_at"],schema="executive")


def downgrade() -> None:
    for table in ["service_health","kpi_values","kpi_definitions","alerts","dashboard_snapshots"]:op.drop_table(table,schema="executive")
    op.execute("DROP SCHEMA IF EXISTS executive")
