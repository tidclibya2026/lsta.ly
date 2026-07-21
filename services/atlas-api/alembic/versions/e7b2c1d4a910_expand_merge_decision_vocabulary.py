"""expand merge decision vocabulary

Revision ID: e7b2c1d4a910
Revises: d3f40a91b672
"""

from alembic import op

revision = "e7b2c1d4a910"
down_revision = "d3f40a91b672"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_merge_decisions_merge_decision_value"
LEGACY_VALUES = (
    "approved_merge",
    "rejected_match",
    "needs_field_verification",
    "create_from_excel",
    "create_from_kml",
    "keep_separate",
    "duplicate_excel",
    "duplicate_kml",
    "deferred",
)
CURRENT_VALUES = LEGACY_VALUES + ("accepted", "rejected", "needs_correction")


def _check(values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{value}'" for value in values)
    return f"decision IN ({quoted})"


def upgrade() -> None:
    op.execute(f"ALTER TABLE staging.merge_decisions DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE staging.merge_decisions ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(CURRENT_VALUES)})"
    )


def downgrade() -> None:
    op.execute("UPDATE staging.merge_decisions SET decision='approved_merge' WHERE decision='accepted'")
    op.execute("UPDATE staging.merge_decisions SET decision='rejected_match' WHERE decision='rejected'")
    op.execute(
        "UPDATE staging.merge_decisions SET decision='needs_field_verification' "
        "WHERE decision='needs_correction'"
    )
    op.execute(f"ALTER TABLE staging.merge_decisions DROP CONSTRAINT {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE staging.merge_decisions ADD CONSTRAINT {CONSTRAINT} CHECK ({_check(LEGACY_VALUES)})"
    )
