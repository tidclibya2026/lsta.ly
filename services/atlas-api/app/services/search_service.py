from __future__ import annotations

import html
import time
from typing import Any, Literal

from geoalchemy2 import Geography
from sqlalchemy import cast, func, or_, select
from sqlalchemy.orm import Session

from app.models import ImportFeature, MediaAsset, Municipality, PublicationRecord, Site, SiteCategory, SiteGeometry
from app.services.arabic_text_service import normalize_arabic_text, prepare_search_query


def highlight_matches(text: str | None, query: str) -> str | None:
    if not text:
        return text
    escaped = html.escape(text)
    for term in query.split():
        if term:
            escaped = escaped.replace(html.escape(term), f"<mark>{html.escape(term)}</mark>")
    return escaped


def calculate_relevance_score(
    *,
    query: str,
    national_id: str | None,
    name_ar: str | None,
    name_en: str | None,
    description: str | None,
    auxiliary: str = "",
    similarity: float = 0,
    full_text_rank: float = 0,
    approved: bool = False,
    internal: bool = False,
    staging: bool = False,
) -> tuple[float, list[str]]:
    q = normalize_arabic_text(query)
    ar = normalize_arabic_text(name_ar or "")
    en = (name_en or "").lower()
    matched: list[str] = []
    score = 0.0
    if national_id and query.upper() == national_id.upper():
        score, matched = 100, ["national_id"]
    elif q and q == ar:
        score, matched = 95, ["name_ar"]
    elif query.lower() == en and en:
        score, matched = 90, ["name_en"]
    elif ar.startswith(q) or en.startswith(query.lower()):
        score, matched = 85, ["name"]
    elif similarity > 0:
        score, matched = min(80, similarity * 80), ["name"]
    if full_text_rank > 0:
        score = max(score, min(70, 40 + full_text_rank * 30))
        matched.append("full_text")
    if q and q in normalize_arabic_text(description or ""):
        score = max(score, 55)
        matched.append("description")
    if q and q in normalize_arabic_text(auxiliary):
        score = max(score, 45)
        matched.append("metadata")
    score += 5 if approved else 0
    score += 3 if internal else 0
    score -= 5 if staging else 0
    return round(min(100, score), 2), list(dict.fromkeys(matched))


def _spatial_filters(
    query: Any,
    geometry: Any,
    *,
    center_lat: float | None,
    center_lon: float | None,
    radius_meters: float | None,
    bbox: tuple[float, float, float, float] | None,
) -> tuple[Any, Any]:
    centroid = func.ST_Centroid(geometry)
    distance = None
    if bbox:
        query = query.where(func.ST_Intersects(geometry, func.ST_MakeEnvelope(*bbox, 4326)))
    if center_lat is not None and center_lon is not None and radius_meters is not None:
        center = func.ST_SetSRID(func.ST_MakePoint(center_lon, center_lat), 4326)
        query = query.where(
            func.ST_DWithin(cast(centroid, Geography(srid=4326)), cast(center, Geography(srid=4326)), radius_meters)
        )
        distance = func.ST_Distance(cast(centroid, Geography(srid=4326)), cast(center, Geography(srid=4326)))
    return query, distance


def search_registry_sites(
    session: Session,
    query_text: str,
    *,
    limit: int = 20,
    offset: int = 0,
    category: str | None = None,
    municipality: str | None = None,
    geometry_type: str | None = None,
    verification_status: str | None = None,
    publication_status: str | None = None,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_meters: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    q = prepare_search_query(query_text)
    similarity = func.greatest(
        func.similarity(func.coalesce(Site.name_ar, ""), query_text),
        func.similarity(func.coalesce(Site.name_en, ""), query_text),
    )
    rank = func.ts_rank_cd(Site.search_vector, func.plainto_tsquery("simple", query_text))
    centroid = func.ST_Centroid(SiteGeometry.geometry)
    statement = (
        select(
            Site,
            SiteGeometry,
            SiteCategory,
            Municipality,
            similarity.label("similarity"),
            rank.label("rank"),
            func.ST_X(centroid),
            func.ST_Y(centroid),
        )
        .join(SiteGeometry, SiteGeometry.site_id == Site.id)
        .outerjoin(SiteCategory, Site.category_id == SiteCategory.id)
        .outerjoin(Municipality, Site.municipality_id == Municipality.id)
    )
    if len(q) >= 2:
        statement = statement.where(
            or_(
                Site.national_id.ilike(query_text),
                Site.search_vector.op("@@")(func.plainto_tsquery("simple", query_text)),
                similarity >= 0.15,
            )
        )
    elif query_text:
        return []
    if category:
        statement = statement.where(SiteCategory.code == category)
    if municipality:
        statement = statement.where(Municipality.code == municipality)
    if geometry_type:
        statement = statement.where(SiteGeometry.geometry_type == geometry_type)
    if verification_status:
        statement = statement.where(Site.verification_status == verification_status)
    statement, distance = _spatial_filters(
        statement,
        SiteGeometry.geometry,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_meters=radius_meters,
        bbox=bbox,
    )
    if distance is not None:
        statement = statement.add_columns(distance.label("distance"))
    rows = session.execute(statement.limit(min(limit + offset, 100)))
    results = []
    for row in rows:
        site, geometry, cat, muni, sim, ft_rank, lng, lat = row[:8]
        meters = float(row[8]) if len(row) > 8 else None
        publication = (
            session.scalar(
                select(PublicationRecord.publication_status)
                .where(PublicationRecord.site_id == site.id)
                .order_by(PublicationRecord.published_at.desc().nullslast())
                .limit(1)
            )
            or "internal"
        )
        if publication_status and publication != publication_status:
            continue
        score, fields = calculate_relevance_score(
            query=query_text,
            national_id=site.national_id,
            name_ar=site.name_ar,
            name_en=site.name_en,
            description=site.description,
            auxiliary=f"{cat.name_ar if cat else ''} {muni.name_ar if muni else ''}",
            similarity=float(sim or 0),
            full_text_rank=float(ft_rank or 0),
            approved=site.verification_status == "approved",
            internal=publication == "internal",
        )
        image = session.scalar(
            select(MediaAsset.url).where(MediaAsset.site_id == site.id, MediaAsset.is_primary.is_(True)).limit(1)
        )
        results.append(
            {
                "result_type": "site",
                "source": "registry",
                "national_id": site.national_id,
                "feature_id": None,
                "name_ar": site.name_ar,
                "name_en": site.name_en,
                "normalized_name": site.normalized_name_ar or normalize_arabic_text(site.name_ar),
                "description_excerpt": (site.description or "")[:240],
                "geometry_type": geometry.geometry_type,
                "category": cat.name_ar if cat else None,
                "municipality": muni.name_ar if muni else None,
                "verification_status": site.verification_status,
                "publication_status": publication,
                "primary_image": image,
                "has_images": image is not None,
                "has_documents": False,
                "image_count": 1 if image else 0,
                "distance_meters": round(meters, 1) if meters is not None else None,
                "relevance_score": score,
                "matched_fields": fields,
                "highlighted_name": highlight_matches(site.name_ar, query_text),
                "highlighted_description": highlight_matches((site.description or "")[:240], query_text),
                "map_geometry_summary": {"centroid": [float(lng), float(lat)]},
                "centroid": [float(lng), float(lat)],
                "bbox": None,
                "review_status": None,
                "quality_score": float(site.profile_completeness_score) if site.profile_completeness_score else None,
                "detail_url": f"/sites/{site.national_id}",
                "is_review_data": False,
            }
        )
    return sorted(results, key=lambda item: item["relevance_score"], reverse=True)[offset : offset + limit]


def search_staging_features(
    session: Session,
    query_text: str,
    *,
    limit: int = 20,
    offset: int = 0,
    geometry_type: str | None = None,
    verification_status: str | None = None,
    has_images: bool | None = None,
    has_name: bool | None = None,
    center_lat: float | None = None,
    center_lon: float | None = None,
    radius_meters: float | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    q = prepare_search_query(query_text)
    similarity = func.similarity(func.coalesce(ImportFeature.name_ar, ""), query_text)
    rank = func.ts_rank_cd(ImportFeature.search_vector, func.plainto_tsquery("simple", query_text))
    centroid = func.ST_Centroid(ImportFeature.geometry)
    statement = select(
        ImportFeature, similarity.label("similarity"), rank.label("rank"), func.ST_X(centroid), func.ST_Y(centroid)
    ).where(func.ST_IsValid(ImportFeature.geometry))
    if len(q) >= 2:
        statement = statement.where(
            or_(
                ImportFeature.source_feature_id.ilike(query_text),
                ImportFeature.search_vector.op("@@")(func.plainto_tsquery("simple", query_text)),
                similarity >= 0.15,
            )
        )
    elif query_text:
        return []
    if geometry_type:
        statement = statement.where(ImportFeature.geometry_type == geometry_type)
    if verification_status:
        statement = statement.where(ImportFeature.review_status == verification_status)
    if has_name is not None:
        statement = statement.where(ImportFeature.missing_name.is_(not has_name))
    if has_images is not None:
        count = func.jsonb_array_length(ImportFeature.properties["image_urls"])
        statement = statement.where(count > 0 if has_images else count == 0)
    statement, distance = _spatial_filters(
        statement,
        ImportFeature.geometry,
        center_lat=center_lat,
        center_lon=center_lon,
        radius_meters=radius_meters,
        bbox=bbox,
    )
    if distance is not None:
        statement = statement.add_columns(distance.label("distance"))
    rows = session.execute(statement.order_by(similarity.desc()).limit(min(limit + offset, 100)))
    results = []
    for row in rows:
        feature, sim, ft_rank, lng, lat = row[:5]
        meters = float(row[5]) if len(row) > 5 else None
        props = feature.properties or {}
        description = props.get("description_text") or ""
        images = props.get("image_urls") or []
        score, fields = calculate_relevance_score(
            query=query_text,
            national_id=None,
            name_ar=feature.name_ar,
            name_en=props.get("name_en"),
            description=description,
            auxiliary=f"{props.get('folder_name', '')} {(props.get('extended_data') or {}).get('النوع', '')}",
            similarity=float(sim or 0),
            full_text_rank=float(ft_rank or 0),
            staging=True,
        )
        results.append(
            {
                "result_type": "feature",
                "source": "staging",
                "national_id": None,
                "feature_id": str(feature.id),
                "name_ar": feature.name_ar,
                "name_en": props.get("name_en"),
                "normalized_name": feature.normalized_name_ar or normalize_arabic_text(feature.name_ar or ""),
                "description_excerpt": description[:240],
                "geometry_type": feature.geometry_type,
                "category": (props.get("extended_data") or {}).get("النوع"),
                "municipality": props.get("municipality"),
                "verification_status": feature.review_status,
                "publication_status": "internal_review",
                "primary_image": images[0] if images else None,
                "has_images": bool(images),
                "has_documents": bool(props.get("documents")),
                "image_count": len(images),
                "distance_meters": round(meters, 1) if meters is not None else None,
                "relevance_score": score,
                "matched_fields": fields,
                "highlighted_name": highlight_matches(feature.name_ar, query_text),
                "highlighted_description": highlight_matches(description[:240], query_text),
                "map_geometry_summary": {"centroid": [float(lng), float(lat)]},
                "centroid": [float(lng), float(lat)],
                "bbox": None,
                "review_status": feature.review_status,
                "quality_score": props.get("quality_score"),
                "detail_url": f"/review/{feature.id}",
                "is_review_data": True,
            }
        )
    return sorted(results, key=lambda item: item["relevance_score"], reverse=True)[offset : offset + limit]


def unified_search(
    session: Session,
    query_text: str,
    *,
    source: Literal["registry", "staging", "all"] = "all",
    limit: int = 20,
    offset: int = 0,
    **filters: Any,
) -> dict[str, Any]:
    started = time.perf_counter()
    pool: list[dict[str, Any]] = []
    fetch = min(100, limit + offset)
    if source in {"registry", "all"}:
        pool.extend(search_registry_sites(session, query_text, limit=fetch, offset=0, **filters))
    if source in {"staging", "all"}:
        pool.extend(search_staging_features(session, query_text, limit=fetch, offset=0, **filters))
    minimum_quality = filters.get("minimum_quality_score")
    if minimum_quality is not None:
        pool = [item for item in pool if float(item.get("quality_score") or 0) >= float(minimum_quality)]
    if filters.get("has_documents") is not None:
        pool = [item for item in pool if bool(item.get("has_documents")) is bool(filters["has_documents"])]
    pool.sort(key=lambda item: (item["relevance_score"], item["source"] == "registry"), reverse=True)
    page = pool[offset : offset + limit]
    total_count = len(pool)
    return {
        "items": page,
        "total": total_count,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total_count,
        "applied_filters": {key: value for key, value in filters.items() if value is not None},
        "query_time_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def autocomplete(
    session: Session, query_text: str, *, source: str = "all", limit: int = 10, include_national_id: bool = True
) -> list[dict[str, Any]]:
    if len(prepare_search_query(query_text)) < 2:
        return []
    results = unified_search(session, query_text, source=source, limit=min(limit, 10), offset=0)["items"]
    return [
        {
            "label": item["name_ar"] or item["name_en"],
            "secondary_label": item["national_id"] or item["geometry_type"],
            "type": item["result_type"],
            "source": item["source"],
            "national_id": item["national_id"] if include_national_id else None,
            "feature_id": item["feature_id"],
            "score": item["relevance_score"],
            "detail_url": item["detail_url"],
        }
        for item in results
    ]


def spatial_search(session: Session, **kwargs: Any) -> dict[str, Any]:
    return unified_search(session, "", **kwargs)


def faceted_search(session: Session) -> dict[str, Any]:
    geometry = dict(
        session.execute(select(ImportFeature.geometry_type, func.count()).group_by(ImportFeature.geometry_type)).all()
    )
    verification = dict(
        session.execute(select(ImportFeature.review_status, func.count()).group_by(ImportFeature.review_status)).all()
    )
    category = ImportFeature.properties["extended_data"]["النوع"].astext
    municipality = ImportFeature.properties["municipality"].astext
    category_counts = dict(
        session.execute(
            select(category, func.count())
            .where(category.is_not(None), category != "")
            .group_by(category)
            .order_by(func.count().desc())
            .limit(50)
        ).all()
    )
    municipality_counts = dict(
        session.execute(
            select(municipality, func.count())
            .where(municipality.is_not(None), municipality != "")
            .group_by(municipality)
            .order_by(func.count().desc())
            .limit(50)
        ).all()
    )
    registry_count = int(session.scalar(select(func.count()).select_from(Site)) or 0)
    staging_count = int(session.scalar(select(func.count()).select_from(ImportFeature)) or 0)
    return {
        "source_counts": {"registry": registry_count, "staging": staging_count},
        "geometry_counts": geometry,
        "verification_counts": verification,
        "publication_counts": {"internal": registry_count, "internal_review": staging_count},
        "category_counts": category_counts,
        "municipality_counts": municipality_counts,
    }
