from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models import DuplicateCandidate, QueryStatistic, SavedQuery, SearchLog
from app.services import discovery_service
from app.services.duplicate_detection_service import (
    generate_candidates,
    list_candidates,
    merge_preview,
    review_candidate,
)
from app.services.national_search_service import (
    autocomplete,
    delete_saved_query,
    get_saved_query,
    list_saved_queries,
    rerun_saved_query,
    save_query,
    search,
    suggest,
)
from app.services.search_service import faceted_search
from app.services.similar_sites_service import find_similar_sites

router = APIRouter(prefix="/api/v1/discovery", tags=["national-discovery"])
Role = Annotated[str, Depends(get_reviewer_role)]
PRIVILEGED = {"data_manager", "system_admin"}
STAGING_ROLES = {"editor", "reviewer", "gis_specialist", *PRIVILEGED}


def _source(requested: str, role: str) -> str:
    if role == "viewer": return "registry"
    if requested in {"metadata", "media"} and role not in PRIVILEGED: raise HTTPException(403, "هذا المصدر مخصص لإدارة البيانات")
    return requested


def _row(row: Any) -> dict[str, Any]:
    return {column.name: (str(value) if isinstance(value := getattr(row, column.name), UUID) else float(value) if hasattr(value, "as_integer_ratio") and not isinstance(value, (int, float)) else value) for column in row.__table__.columns}


class SavedSearchIn(BaseModel):
    query_name: str = Field(min_length=1, max_length=300)
    query_text: str = ""
    filters: dict[str, Any] = {}
    spatial_filter: dict[str, Any] | None = None
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] | None = None
    is_shared: bool = False


class DuplicateDecision(BaseModel):
    decision: Literal["pending_review", "confirmed_duplicate", "not_duplicate", "ignored"]
    notes: str | None = None


@router.get("/search")
def discovery_search(role: Role, q: str = "", source: Literal["registry", "staging", "metadata", "media", "all"] = "all", category: str | None = None, municipality: str | None = None, geometry_type: str | None = None, verification_status: str | None = None, publication_status: str | None = None, review_status: str | None = None, has_images: bool | None = None, has_documents: bool | None = None, minimum_quality_score: float | None = Query(None, ge=0, le=100), minimum_completeness_score: float | None = Query(None, ge=0, le=100), center_lat: float | None = Query(None, ge=-90, le=90), center_lon: float | None = Query(None, ge=-180, le=180), radius_meters: float | None = Query(None, gt=0, le=100000), bbox: str | None = None, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), sort_by: str = "relevance", sort_order: Literal["asc", "desc"] = "desc", view_mode: str = "list", db: Session = Depends(get_db)):
    if q and len(q.strip()) < 2 and center_lat is None and not bbox: return {"items": [], "total_count": 0, "limit": limit, "offset": offset, "has_more": False, "query_time_ms": 0.0, "applied_filters": {}}
    if (center_lat is None) != (center_lon is None): raise HTTPException(422, "يلزم تحديد خط العرض والطول معًا")
    bounds = tuple(map(float, bbox.split(","))) if bbox else None
    if bounds and len(bounds) != 4: raise HTTPException(422, "bbox غير صالح")
    effective = _source(source, role)
    kwargs = {"category": category, "municipality": municipality, "geometry_type": geometry_type, "verification_status": verification_status or review_status, "publication_status": publication_status, "has_images": has_images, "minimum_quality_score": minimum_quality_score or minimum_completeness_score, "center_lat": center_lat, "center_lon": center_lon, "radius_meters": radius_meters, "bbox": bounds, "limit": limit, "offset": offset}
    result = search(db, q, role=role, source=effective, **kwargs); db.commit(); return result


@router.get("/autocomplete")
def discovery_autocomplete(role: Role, q: str, source: str = "all", limit: int = Query(10, ge=1, le=10), db: Session = Depends(get_db)): return {"items": autocomplete(db, q, source=_source(source, role), limit=limit) if len(q.strip()) >= 2 else []}


@router.get("/suggestions")
def discovery_suggestions(role: Role, q: str, db: Session = Depends(get_db)): return {"items": [_row(item) for item in suggest(db, q)] or autocomplete(db, q, source=_source("all", role), limit=5)}


@router.get("/facets")
def discovery_facets(role: Role, db: Session = Depends(get_db)):
    result = faceted_search(db)
    if role == "viewer": result.get("source_counts", {}).pop("staging", None)
    return result


@router.get("/nearby")
def nearby(role: Role, center_lat: float, center_lon: float, radius_meters: float = Query(5000, gt=0, le=100000), source: str = "all", limit: int = Query(20, le=100), db: Session = Depends(get_db)): return discovery_service.discover_nearby(db, center_lat, center_lon, radius_meters, source=_source(source, role), limit=limit, offset=0)
@router.get("/categories")
def categories(role: Role, db: Session = Depends(get_db)): return {"items": faceted_search(db).get("categories", [])}
@router.get("/municipalities")
def municipalities(role: Role, db: Session = Depends(get_db)): return {"items": faceted_search(db).get("municipalities", [])}
@router.get("/high-quality")
def high_quality(role: Role, minimum: float = 70, db: Session = Depends(get_db)): return discovery_service.discover_high_quality(db, minimum, source=_source("all", role), limit=20, offset=0)
@router.get("/incomplete")
def incomplete(role: Role, db: Session = Depends(get_db)): return discovery_service.discover_incomplete_profiles(db, source=_source("all", role), limit=20, offset=0)
@router.get("/missing-media")
def missing_media(role: Role, db: Session = Depends(get_db)): return discovery_service.discover_missing_media(db, source=_source("all", role), limit=20, offset=0)
@router.get("/pending-review")
def pending_review(role: Role, db: Session = Depends(get_db)):
    if role not in STAGING_ROLES: raise HTTPException(403, "بيانات المراجعة داخلية")
    return discovery_service.discover_pending_review(db, limit=20, offset=0)
@router.get("/recent")
def recent(role: Role, db: Session = Depends(get_db)): return discovery_service.discover_recently_updated(db, source=_source("all", role), limit=20, offset=0)


@router.post("/saved-searches", status_code=201)
def create_saved(payload: SavedSearchIn, role: Role, db: Session = Depends(get_db)): row = save_query(db, payload.model_dump()); db.commit(); db.refresh(row); return _row(row)
@router.get("/saved-searches")
def saved(role: Role, db: Session = Depends(get_db)): return {"items": [_row(row) for row in list_saved_queries(db)]}
@router.get("/saved-searches/{query_id}")
def saved_detail(query_id: UUID, role: Role, db: Session = Depends(get_db)):
    row = get_saved_query(db, query_id)
    if not row: raise HTTPException(404, "البحث المحفوظ غير موجود")
    return _row(row)
@router.delete("/saved-searches/{query_id}", status_code=204)
def remove_saved(query_id: UUID, role: Role, db: Session = Depends(get_db)):
    if not delete_saved_query(db, query_id): raise HTTPException(404, "البحث المحفوظ غير موجود")
    db.commit()
@router.post("/saved-searches/{query_id}/run")
def run_saved(query_id: UUID, role: Role, db: Session = Depends(get_db)):
    row = get_saved_query(db, query_id)
    if not row: raise HTTPException(404, "البحث المحفوظ غير موجود")
    result = rerun_saved_query(db, row, role); db.commit(); return result


@router.get("/duplicates")
def duplicates(role: Role, status: str | None = None, db: Session = Depends(get_db)):
    if role not in {"reviewer", *PRIVILEGED}: raise HTTPException(403, "مراجعة التكرار غير مسموحة")
    return {"items": [_row(row) for row in list_candidates(db, status)]}
@router.post("/duplicates/generate")
def generate(role: Role, db: Session = Depends(get_db)):
    if role not in PRIVILEGED: raise HTTPException(403, "توليد المرشحين مخصص لإدارة البيانات")
    rows = generate_candidates(db); db.commit(); return {"generated_count": len(rows), "automatic_merge": False}
@router.get("/duplicates/{candidate_id}")
def duplicate_detail(candidate_id: UUID, role: Role, db: Session = Depends(get_db)):
    row = db.get(DuplicateCandidate, candidate_id)
    if not row: raise HTTPException(404, "المرشح غير موجود")
    return _row(row)
@router.post("/duplicates/{candidate_id}/decision")
def duplicate_decision(candidate_id: UUID, payload: DuplicateDecision, role: Role, db: Session = Depends(get_db)):
    if role not in {"reviewer", *PRIVILEGED}: raise HTTPException(403, "القرار غير مسموح")
    try: row = review_candidate(db, candidate_id, payload.decision, payload.notes)
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc
    db.commit(); return _row(row)
@router.post("/duplicates/{candidate_id}/merge-preview")
def duplicate_merge_preview(candidate_id: UUID, role: Role, db: Session = Depends(get_db)):
    row = db.get(DuplicateCandidate, candidate_id)
    if not row: raise HTTPException(404, "المرشح غير موجود")
    return merge_preview(row)


@router.get("/sites/{national_id}/similar")
def similar(national_id: str, role: Role, db: Session = Depends(get_db)):
    try: return {"items": find_similar_sites(db, national_id)}
    except LookupError as exc: raise HTTPException(404, str(exc)) from exc


def _analytics(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc); today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {"searches_today": db.scalar(select(func.count()).select_from(SearchLog).where(SearchLog.created_at >= today)) or 0, "searches_this_week": db.scalar(select(func.count()).select_from(SearchLog).where(SearchLog.created_at >= now - timedelta(days=7))) or 0, "average_query_time_ms": float(db.scalar(select(func.avg(SearchLog.query_time_ms))) or 0), "saved_searches_count": db.scalar(select(func.count()).select_from(SavedQuery).where(SavedQuery.is_active.is_(True))) or 0, "search_logs_count": db.scalar(select(func.count()).select_from(SearchLog)) or 0}
@router.get("/analytics/summary")
def analytics(role: Role, db: Session = Depends(get_db)):
    if role not in {"decision_maker", *PRIVILEGED}: raise HTTPException(403, "تحليلات البحث غير مسموحة")
    return _analytics(db)
@router.get("/analytics/top-queries")
def top_queries(role: Role, db: Session = Depends(get_db)):
    if role not in {"decision_maker", *PRIVILEGED}: raise HTTPException(403, "تحليلات البحث غير مسموحة")
    return {"items": [_row(row) for row in db.scalars(select(QueryStatistic).order_by(QueryStatistic.total_searches.desc()).limit(20))]}
@router.get("/analytics/no-results")
def no_results(role: Role, db: Session = Depends(get_db)):
    if role not in {"decision_maker", *PRIVILEGED}: raise HTTPException(403, "تحليلات البحث غير مسموحة")
    return {"items": [_row(row) for row in db.scalars(select(QueryStatistic).where(QueryStatistic.no_result_searches > 0).order_by(QueryStatistic.no_result_searches.desc()).limit(20))]}
@router.get("/analytics/query-performance")
def query_performance(role: Role, db: Session = Depends(get_db)):
    if role not in {"decision_maker", *PRIVILEGED}: raise HTTPException(403, "تحليلات البحث غير مسموحة")
    return _analytics(db)
