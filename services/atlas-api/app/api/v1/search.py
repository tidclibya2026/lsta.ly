from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.services.arabic_text_service import normalize_arabic_text
from app.services.search_service import autocomplete, faceted_search, unified_search

router = APIRouter(prefix="/api/v1/search", tags=["national-search"])
Role = Annotated[str, Depends(get_reviewer_role)]


def parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    try:
        parts = tuple(float(item) for item in value.split(","))
    except ValueError as exc:
        raise HTTPException(422, "bbox غير صالح") from exc
    if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
        raise HTTPException(422, "bbox يجب أن يكون minLon,minLat,maxLon,maxLat")
    return parts  # type: ignore[return-value]


def visible_source(requested: str, role: str) -> str:
    can_stage = role in {"reviewer", "gis_specialist", "editor", "data_manager", "system_admin"}
    if requested == "staging" and not can_stage:
        raise HTTPException(403, "لا توجد صلاحية لعرض Staging")
    return requested if can_stage else "registry"


@router.get("")
def search(
    role: Role,
    q: str = "",
    source: Literal["registry", "staging", "all"] = "all",
    category: str | None = None,
    municipality: str | None = None,
    geometry_type: str | None = None,
    verification_status: str | None = None,
    publication_status: str | None = None,
    has_images: bool | None = None,
    has_name: bool | None = None,
    minimum_quality_score: float | None = Query(None, ge=0, le=100),
    center_lat: float | None = Query(None, ge=-90, le=90),
    center_lon: float | None = Query(None, ge=-180, le=180),
    radius_meters: float | None = Query(None, gt=0, le=100000),
    bbox: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = "relevance",
    sort_order: Literal["asc", "desc"] = "desc",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if (center_lat is None) != (center_lon is None) or (radius_meters is not None and center_lat is None):
        raise HTTPException(422, "يلزم center_lat وcenter_lon معًا")
    if center_lat is not None and radius_meters is None:
        radius_meters = 5000
    if len(normalize_arabic_text(q)) < 2 and center_lat is None and bbox is None:
        return {"items": [], "total": 0, "limit": limit, "offset": offset, "query_time_ms": 0.0}
    result = unified_search(
        db,
        q,
        source=visible_source(source, role),
        category=category,
        municipality=municipality,
        geometry_type=geometry_type,
        verification_status=verification_status,
        publication_status=publication_status,
        has_images=has_images,
        has_name=has_name,
        minimum_quality_score=minimum_quality_score,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_meters=radius_meters,
        bbox=parse_bbox(bbox),
        limit=limit,
        offset=offset,
    )
    if sort_by == "distance":
        result["items"].sort(
            key=lambda item: item["distance_meters"] if item["distance_meters"] is not None else float("inf"),
            reverse=sort_order == "desc",
        )
    return result


@router.get("/autocomplete")
def search_autocomplete(
    role: Role,
    q: str,
    source: Literal["registry", "staging", "all"] = "all",
    limit: int = Query(10, ge=1, le=10),
    include_national_id: bool = True,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return {
        "items": autocomplete(
            db, q, source=visible_source(source, role), limit=limit, include_national_id=include_national_id
        )
    }


@router.get("/nearby")
def nearby(
    role: Role,
    center_lat: float = Query(..., ge=-90, le=90),
    center_lon: float = Query(..., ge=-180, le=180),
    radius_meters: float = Query(5000, gt=0, le=100000),
    source: Literal["registry", "staging", "all"] = "all",
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return unified_search(
        db,
        "",
        source=visible_source(source, role),
        center_lat=center_lat,
        center_lon=center_lon,
        radius_meters=radius_meters,
        limit=limit,
        offset=offset,
    )


@router.get("/facets")
def facets(role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    values = faceted_search(db)
    if role == "viewer":
        values["source_counts"].pop("staging", None)
    return values


@router.get("/suggestions")
def suggestions(role: Role, q: str, db: Session = Depends(get_db)) -> dict[str, object]:
    normalized = normalize_arabic_text(q)
    items = autocomplete(db, normalized, source=visible_source("all", role), limit=5)
    return {
        "corrected_query": normalized,
        "alternative_terms": list(dict.fromkeys(item["label"] for item in items if item["label"])),
        "likely_entities": items,
        "did_you_mean": items[0]["label"] if items and items[0]["label"] != q else None,
    }
