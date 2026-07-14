from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SiteQualitySnapshot


def save_quality_snapshot(
    session: Session,
    site_id: uuid.UUID,
    *,
    overall_score: float,
    score_breakdown: dict[str, Any],
    critical_issues: list[Any],
    warnings: list[Any],
    calculated_by: str,
    source_version: str | None = None,
) -> SiteQualitySnapshot:
    snapshot = SiteQualitySnapshot(
        site_id=site_id,
        overall_score=overall_score,
        score_breakdown=score_breakdown,
        critical_issues=critical_issues,
        warnings=warnings,
        calculated_by=calculated_by,
        source_version=source_version,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def list_quality_snapshots(session: Session, site_id: uuid.UUID) -> list[SiteQualitySnapshot]:
    return list(
        session.scalars(
            select(SiteQualitySnapshot)
            .where(SiteQualitySnapshot.site_id == site_id)
            .order_by(SiteQualitySnapshot.calculated_at.desc())
        )
    )
