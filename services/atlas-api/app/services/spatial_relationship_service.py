from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import AuditLog, ImportFeature, Site, SiteCategory, SiteGeometry, SiteRelationship

RELATIONSHIP_TYPES = {
    "nearby",
    "part_of",
    "contains",
    "related_to",
    "route_connection",
    "service_for",
    "investment_related",
    "heritage_related",
    "accommodation_nearby",
    "food_service_nearby",
    "airport_nearby",
    "administrative_relation",
}
SOURCE_METHODS = {"manual", "spatial_query", "imported", "system_generated"}


def _site_geometry(session: Session, site_id: uuid.UUID) -> SiteGeometry:
    geometry = session.scalar(
        select(SiteGeometry).where(SiteGeometry.site_id == site_id).order_by(SiteGeometry.id).limit(1)
    )
    if geometry is None:
        raise LookupError("لا توجد هندسة للموقع")
    return geometry


def find_nearby_registry_sites(
    session: Session,
    site_id: uuid.UUID,
    *,
    radius_meters: float,
    category: str | None = None,
    geometry_type: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    source = _site_geometry(session, site_id)
    source_geography = func.ST_Centroid(source.geometry).cast(type_=source.geometry.type)
    target_geography = func.ST_Centroid(SiteGeometry.geometry).cast(type_=SiteGeometry.geometry.type)
    distance = func.ST_DistanceSphere(target_geography, source_geography)
    query = (
        select(
            Site,
            SiteGeometry,
            distance.label("distance"),
            func.ST_X(target_geography).label("lng"),
            func.ST_Y(target_geography).label("lat"),
        )
        .join(SiteGeometry, SiteGeometry.site_id == Site.id)
        .where(
            Site.id != site_id,
            func.ST_DWithin(
                cast(target_geography, Geography(srid=4326)),
                cast(source_geography, Geography(srid=4326)),
                radius_meters,
            ),
            distance <= radius_meters,
        )
    )
    if category:
        query = query.join(SiteCategory, Site.category_id == SiteCategory.id).where(SiteCategory.code == category)
    if geometry_type:
        query = query.where(SiteGeometry.geometry_type == geometry_type)
    rows = session.execute(query.order_by(distance).limit(min(limit, 100)))
    return [
        {
            "target_type": "registry",
            "target_id": str(site.id),
            "national_id": site.national_id,
            "name": site.name_ar,
            "geometry_type": geometry.geometry_type,
            "distance_meters": round(float(meters), 1),
            "review_status": site.verification_status,
            "quality_issues": [],
            "longitude": float(lng),
            "latitude": float(lat),
        }
        for site, geometry, meters, lng, lat in rows
    ]


def find_nearby_staging_features(
    session: Session,
    site_id: uuid.UUID,
    *,
    radius_meters: float,
    geometry_type: str | None = "Point",
    has_name: bool | None = None,
    include_non_points: bool = False,
    limit: int = 25,
) -> list[dict[str, Any]]:
    source = _site_geometry(session, site_id)
    source_center = func.ST_Centroid(source.geometry)
    target_center = func.ST_Centroid(ImportFeature.geometry)
    distance = func.ST_DistanceSphere(target_center, source_center)
    query = select(
        ImportFeature,
        distance.label("distance"),
        func.ST_X(target_center).label("lng"),
        func.ST_Y(target_center).label("lat"),
    ).where(
        func.ST_IsValid(ImportFeature.geometry),
        func.ST_DWithin(
            cast(target_center, Geography(srid=4326)), cast(source_center, Geography(srid=4326)), radius_meters
        ),
        distance <= radius_meters,
    )
    if geometry_type:
        query = query.where(ImportFeature.geometry_type == geometry_type)
    elif not include_non_points:
        query = query.where(ImportFeature.geometry_type == "Point")
    if has_name is not None:
        query = query.where(ImportFeature.missing_name.is_(not has_name))
    rows = session.execute(query.order_by(distance).limit(min(limit, 100)))
    return [
        {
            "target_type": "staging",
            "target_id": str(feature.id),
            "feature_id": feature.source_feature_id,
            "name": feature.name_ar,
            "geometry_type": feature.geometry_type,
            "distance_meters": round(float(meters), 1),
            "review_status": feature.review_status,
            "quality_issues": feature.validation_issues or [],
            "longitude": float(lng),
            "latitude": float(lat),
        }
        for feature, meters, lng, lat in rows
    ]


def calculate_distance(session: Session, first_geometry: Any, second_geometry: Any) -> float:
    return float(
        session.scalar(
            select(func.ST_DistanceSphere(func.ST_Centroid(first_geometry), func.ST_Centroid(second_geometry)))
        )
        or 0
    )


def calculate_bearing(session: Session, first_geometry: Any, second_geometry: Any) -> float:
    return float(
        session.scalar(
            select(func.degrees(func.ST_Azimuth(func.ST_Centroid(first_geometry), func.ST_Centroid(second_geometry))))
        )
        or 0
    )


def _create_relationship(
    session: Session,
    source_site_id: uuid.UUID,
    *,
    relationship_type: str,
    source_method: str,
    target_site_id: uuid.UUID | None = None,
    target_staging_feature_id: uuid.UUID | None = None,
    distance_meters: float | None = None,
    confidence_score: float | None = None,
    metadata: dict[str, Any] | None = None,
    created_by: uuid.UUID | None = None,
) -> SiteRelationship:
    if relationship_type not in RELATIONSHIP_TYPES or source_method not in SOURCE_METHODS:
        raise ValueError("نوع العلاقة أو مصدرها غير صالح")
    if bool(target_site_id) == bool(target_staging_feature_id):
        raise ValueError("يجب تحديد هدف واحد فقط")
    if target_site_id == source_site_id:
        raise ValueError("لا يمكن ربط الموقع بنفسه")
    duplicate_filters = [
        SiteRelationship.source_site_id == source_site_id,
        SiteRelationship.relationship_type == relationship_type,
    ]
    duplicate_filters.append(
        SiteRelationship.target_site_id == target_site_id
        if target_site_id
        else SiteRelationship.target_staging_feature_id == target_staging_feature_id
    )
    if session.scalar(select(SiteRelationship.id).where(*duplicate_filters)):
        raise ValueError("العلاقة موجودة مسبقًا")
    item = SiteRelationship(
        source_site_id=source_site_id,
        target_site_id=target_site_id,
        target_staging_feature_id=target_staging_feature_id,
        relationship_type=relationship_type,
        source_method=source_method,
        distance_meters=distance_meters,
        confidence_score=confidence_score,
        relationship_metadata=metadata or {},
        verification_status="pending_review",
        publication_status="internal",
        created_by=created_by,
    )
    session.add(item)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError("العلاقة موجودة مسبقًا") from exc
    return item


def create_manual_relationship(session: Session, source_site_id: uuid.UUID, **values: Any) -> SiteRelationship:
    return _create_relationship(session, source_site_id, source_method="manual", **values)


def create_spatial_relationship(session: Session, source_site_id: uuid.UUID, **values: Any) -> SiteRelationship:
    return _create_relationship(session, source_site_id, source_method="spatial_query", **values)


def delete_relationship(session: Session, source_site_id: uuid.UUID, relationship_id: uuid.UUID) -> None:
    item = session.get(SiteRelationship, relationship_id)
    if item is None or item.source_site_id != source_site_id:
        raise LookupError("العلاقة غير موجودة")
    session.delete(item)


def verify_relationship(
    session: Session, source_site_id: uuid.UUID, relationship_id: uuid.UUID, verified_by: uuid.UUID | None = None
) -> SiteRelationship:
    item = session.get(SiteRelationship, relationship_id)
    if item is None or item.source_site_id != source_site_id:
        raise LookupError("العلاقة غير موجودة")
    item.verification_status, item.verified_by, item.verified_at = "approved", verified_by, datetime.now(timezone.utc)
    return item


def reject_relationship(
    session: Session, source_site_id: uuid.UUID, relationship_id: uuid.UUID, verified_by: uuid.UUID | None = None
) -> SiteRelationship:
    item = session.get(SiteRelationship, relationship_id)
    if item is None or item.source_site_id != source_site_id:
        raise LookupError("العلاقة غير موجودة")
    item.verification_status, item.verified_by, item.verified_at = "rejected", verified_by, datetime.now(timezone.utc)
    return item


def list_site_relationships(session: Session, site_id: uuid.UUID) -> list[SiteRelationship]:
    return list(
        session.scalars(
            select(SiteRelationship)
            .where(SiteRelationship.source_site_id == site_id)
            .order_by(SiteRelationship.created_at.desc())
        )
    )


def refresh_nearby_relationships(
    session: Session,
    site: Site,
    *,
    radius_meters: float,
    relationship_type: str,
    source: Literal["registry", "staging", "all"],
    limit: int = 25,
    created_by: uuid.UUID | None = None,
) -> list[SiteRelationship]:
    maximum = min(limit, 50)
    candidates: list[dict[str, Any]] = []
    if source in {"registry", "all"}:
        candidates.extend(find_nearby_registry_sites(session, site.id, radius_meters=radius_meters, limit=maximum))
    if source in {"staging", "all"}:
        candidates.extend(
            find_nearby_staging_features(
                session, site.id, radius_meters=radius_meters, geometry_type="Point", has_name=True, limit=maximum
            )
        )
    candidates.sort(key=lambda item: item["distance_meters"])
    created = []
    for candidate in candidates[:maximum]:
        filters = [SiteRelationship.source_site_id == site.id, SiteRelationship.relationship_type == relationship_type]
        target_values: dict[str, Any]
        if candidate["target_type"] == "registry":
            target_id = uuid.UUID(candidate["target_id"])
            filters.append(SiteRelationship.target_site_id == target_id)
            target_values = {"target_site_id": target_id}
        else:
            target_id = uuid.UUID(candidate["target_id"])
            filters.append(SiteRelationship.target_staging_feature_id == target_id)
            target_values = {"target_staging_feature_id": target_id}
        if session.scalar(select(SiteRelationship.id).where(*filters)):
            continue
        created.append(
            create_spatial_relationship(
                session,
                site.id,
                relationship_type=relationship_type,
                distance_meters=candidate["distance_meters"],
                confidence_score=75,
                metadata={"radius_meters": radius_meters},
                created_by=created_by,
                **target_values,
            )
        )
    session.add(
        AuditLog(
            action="spatial_relationships_refreshed",
            entity_type="site",
            entity_id=site.id,
            details={
                "radius_meters": radius_meters,
                "source": source,
                "created": len(created),
                "relationship_type": relationship_type,
            },
        )
    )
    session.flush()
    return created


def relationship_summary(session: Session, site_id: uuid.UUID) -> dict[str, Any]:
    rows = list_site_relationships(session, site_id)
    return {
        "total": len(rows),
        "pending_review": sum(item.verification_status == "pending_review" for item in rows),
        "approved": sum(item.verification_status == "approved" for item in rows),
        "rejected": sum(item.verification_status == "rejected" for item in rows),
        "registry_targets": sum(item.target_site_id is not None for item in rows),
        "staging_targets": sum(item.target_staging_feature_id is not None for item in rows),
    }


def timed_nearby_query(
    session: Session,
    site: Site,
    *,
    radius_meters: float,
    source: str,
    geometry_type: str | None,
    has_name: bool | None,
    category: str | None,
    limit: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    if source in {"registry", "all"}:
        results.extend(
            find_nearby_registry_sites(
                session,
                site.id,
                radius_meters=radius_meters,
                category=category,
                geometry_type=geometry_type,
                limit=limit,
            )
        )
    if source in {"staging", "all"}:
        results.extend(
            find_nearby_staging_features(
                session,
                site.id,
                radius_meters=radius_meters,
                geometry_type=geometry_type or "Point",
                has_name=has_name,
                include_non_points=geometry_type in {"LineString", "Polygon"},
                limit=limit,
            )
        )
    results.sort(key=lambda item: item["distance_meters"])
    results = results[:limit]
    return {
        "center_site": {"national_id": site.national_id, "name": site.name_ar},
        "radius_meters": radius_meters,
        "total_results": len(results),
        "results": results,
        "query_time_ms": round((time.perf_counter() - started) * 1000, 2),
    }
