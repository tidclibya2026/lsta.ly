from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import MediaAsset, Site, SiteDocument, SiteGeometry, SiteProfile

WEIGHTS = {
    "name_ar": 10,
    "name_en": 5,
    "category": 10,
    "municipality": 10,
    "description": 10,
    "geometry": 15,
    "primary_image": 10,
    "source": 10,
    "approved": 10,
    "profile": 5,
    "document": 5,
}


def calculate_site_completeness(session: Session, site: Site, *, persist: bool = False) -> dict[str, Any]:
    checks = {
        "name_ar": bool(site.name_ar),
        "name_en": bool(site.name_en),
        "category": bool(site.category_id),
        "municipality": bool(site.municipality_id),
        "description": bool(site.description),
        "geometry": bool(
            session.scalar(select(func.count()).select_from(SiteGeometry).where(SiteGeometry.site_id == site.id))
        ),
        "primary_image": bool(
            session.scalar(select(MediaAsset.id).where(MediaAsset.site_id == site.id, MediaAsset.is_primary.is_(True)))
        ),
        "source": bool(site.data_source_id),
        "approved": site.verification_status == "approved",
        "profile": bool(session.scalar(select(SiteProfile.id).where(SiteProfile.site_id == site.id))),
        "document": bool(session.scalar(select(SiteDocument.id).where(SiteDocument.site_id == site.id))),
    }
    breakdown = {
        key: {"earned": WEIGHTS[key] if value else 0, "weight": WEIGHTS[key], "passed": value}
        for key, value in checks.items()
    }
    score = sum(item["earned"] for item in breakdown.values())
    if persist:
        site.profile_completeness_score = score
    return {"score": score, "breakdown": breakdown}
