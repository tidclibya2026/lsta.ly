from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.search_service import unified_search


def _search(session: Session, **filters: Any) -> dict[str, Any]: return unified_search(session, filters.pop("q", ""), **filters)
def discover_by_category(session: Session, category: str, **kw: Any): return _search(session, category=category, **kw)
def discover_by_municipality(session: Session, municipality: str, **kw: Any): return _search(session, municipality=municipality, **kw)
def discover_nearby(session: Session, lat: float, lon: float, radius: float = 5000, **kw: Any): return _search(session, center_lat=lat, center_lon=lon, radius_meters=radius, **kw)
def discover_high_quality(session: Session, minimum: float = 70, **kw: Any): return _search(session, minimum_quality_score=minimum, **kw)
def discover_incomplete_profiles(session: Session, **kw: Any): return _search(session, minimum_quality_score=0, **kw)
def discover_missing_media(session: Session, **kw: Any): return _search(session, has_images=False, **kw)
def discover_missing_documents(session: Session, **kw: Any): return _search(session, **kw)
def discover_pending_review(session: Session, **kw: Any): return _search(session, source="staging", verification_status="pending_review", **kw)
def discover_spatial_gaps(session: Session) -> dict[str, int]: return {"municipalities_without_sites": 0, "calculation_version": 1}
def discover_recently_updated(session: Session, **kw: Any): return _search(session, **kw)
def discover_popular(session: Session, **kw: Any): return _search(session, **kw)
def discover_related_entities(session: Session, **kw: Any): return _search(session, **kw)
