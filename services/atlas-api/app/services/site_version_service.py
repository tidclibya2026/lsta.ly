from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Site, SiteProfile, SiteVersion


def _site_snapshot(session: Session, site: Site) -> dict[str, Any]:
    profile = session.scalar(select(SiteProfile).where(SiteProfile.site_id == site.id))
    return {
        "site": {
            "national_id": site.national_id,
            "name_ar": site.name_ar,
            "name_en": site.name_en,
            "description": site.description,
            "verification_status": site.verification_status,
            "slug": site.slug,
        },
        "profile": None
        if profile is None
        else {
            column.name: getattr(profile, column.name)
            for column in SiteProfile.__table__.columns
            if column.name not in {"id", "site_id", "created_at", "updated_at"}
        },
    }


def create_version_snapshot(
    session: Session, site: Site, change_summary: str, created_by: uuid.UUID | None = None
) -> SiteVersion:
    number = (
        int(
            session.scalar(
                select(func.coalesce(func.max(SiteVersion.version_number), 0)).where(SiteVersion.site_id == site.id)
            )
            or 0
        )
        + 1
    )
    version = SiteVersion(
        site_id=site.id,
        version_number=number,
        snapshot=_site_snapshot(session, site),
        change_summary=change_summary,
        created_by=created_by,
    )
    session.add(version)
    session.flush()
    return version


def list_versions(session: Session, site_id: uuid.UUID) -> list[SiteVersion]:
    return list(
        session.scalars(
            select(SiteVersion).where(SiteVersion.site_id == site_id).order_by(SiteVersion.version_number.desc())
        )
    )


def get_version(session: Session, site_id: uuid.UUID, version_number: int) -> SiteVersion:
    version = session.scalar(
        select(SiteVersion).where(SiteVersion.site_id == site_id, SiteVersion.version_number == version_number)
    )
    if version is None:
        raise LookupError("الإصدار غير موجود")
    return version


def compare_versions(session: Session, site_id: uuid.UUID, first: int, second: int) -> dict[str, Any]:
    left, right = get_version(session, site_id, first), get_version(session, site_id, second)
    keys = set(left.snapshot) | set(right.snapshot)
    return {
        key: {"before": left.snapshot.get(key), "after": right.snapshot.get(key)}
        for key in keys
        if left.snapshot.get(key) != right.snapshot.get(key)
    }
