from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Municipality, Site, SiteCategory


def find_similar_sites(session: Session, national_id: str, limit: int = 10) -> list[dict[str, object]]:
    source = session.scalar(select(Site).where(Site.national_id == national_id))
    if not source: raise LookupError("site not found")
    rows = session.execute(select(Site, SiteCategory, Municipality).outerjoin(SiteCategory, Site.category_id == SiteCategory.id).outerjoin(Municipality, Site.municipality_id == Municipality.id).where(Site.id != source.id).limit(limit))
    result = []
    for site, category, municipality in rows:
        cat = bool(source.category_id and source.category_id == site.category_id)
        muni = bool(source.municipality_id and source.municipality_id == site.municipality_id)
        score = (45 if cat else 0) + (20 if muni else 0)
        result.append({"national_id": site.national_id, "name_ar": site.name_ar, "similarity_score": score, "similarity_breakdown": {"category": 45 if cat else 0, "municipality": 20 if muni else 0}, "reasons": [label for match, label in ((cat, "نفس الفئة"), (muni, "نفس البلدية")) if match], "distance_meters": None, "category": category.name_ar if category else None, "municipality": municipality.name_ar if municipality else None})
    return sorted(result, key=lambda row: row["similarity_score"], reverse=True)


def calculate_site_similarity(*args, **kwargs):  # compatibility entry point
    return find_similar_sites(*args, **kwargs)
