from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Site, SiteGeometry, SiteRelationship

RELATIONSHIP_TYPES = {
    "nearby",
    "part_of",
    "contains",
    "related_to",
    "route_connection",
    "service_for",
    "investment_related",
    "heritage_related",
    "administrative_relation",
}


def create_relationship(
    session: Session, source_site_id: uuid.UUID, target_site_id: uuid.UUID, relationship_type: str, **values: Any
) -> SiteRelationship:
    if source_site_id == target_site_id:
        raise ValueError("لا يمكن ربط الموقع بنفسه")
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError("نوع العلاقة غير صالح")
    if session.get(Site, target_site_id) is None:
        raise LookupError("الموقع الهدف غير موجود")
    existing = session.scalar(
        select(SiteRelationship).where(
            SiteRelationship.source_site_id == source_site_id,
            SiteRelationship.target_site_id == target_site_id,
            SiteRelationship.relationship_type == relationship_type,
        )
    )
    if existing:
        raise ValueError("العلاقة موجودة مسبقًا")
    item = SiteRelationship(
        source_site_id=source_site_id, target_site_id=target_site_id, relationship_type=relationship_type, **values
    )
    session.add(item)
    session.flush()
    return item


def delete_relationship(session: Session, source_site_id: uuid.UUID, relationship_id: uuid.UUID) -> None:
    item = session.get(SiteRelationship, relationship_id)
    if item is None or item.source_site_id != source_site_id:
        raise LookupError("العلاقة غير موجودة")
    session.delete(item)


def list_relationships(session: Session, site_id: uuid.UUID) -> list[SiteRelationship]:
    return list(
        session.scalars(
            select(SiteRelationship)
            .where(or_(SiteRelationship.source_site_id == site_id, SiteRelationship.target_site_id == site_id))
            .order_by(SiteRelationship.relationship_type)
        )
    )


def calculate_nearby_sites(session: Session, site_id: uuid.UUID, radius_meters: float = 1000) -> list[dict[str, Any]]:
    source = session.scalar(
        select(SiteGeometry).where(SiteGeometry.site_id == site_id).order_by(SiteGeometry.id).limit(1)
    )
    if source is None:
        return []
    distance = func.ST_DistanceSphere(func.ST_Centroid(SiteGeometry.geometry), func.ST_Centroid(source.geometry))
    rows = session.execute(
        select(Site, distance.label("distance"))
        .join(SiteGeometry, SiteGeometry.site_id == Site.id)
        .where(Site.id != site_id, distance <= radius_meters)
        .order_by(distance)
    )
    return [
        {
            "site_id": str(site.id),
            "national_id": site.national_id,
            "name_ar": site.name_ar,
            "distance_meters": round(float(meters), 1),
        }
        for site, meters in rows
    ]


def refresh_spatial_relationships(
    session: Session, site_id: uuid.UUID, radius_meters: float = 1000
) -> list[SiteRelationship]:
    created = []
    for candidate in calculate_nearby_sites(session, site_id, radius_meters):
        target_id = uuid.UUID(candidate["site_id"])
        exists_item = session.scalar(
            select(SiteRelationship.id).where(
                SiteRelationship.source_site_id == site_id,
                SiteRelationship.target_site_id == target_id,
                SiteRelationship.relationship_type == "nearby",
            )
        )
        if not exists_item:
            created.append(
                create_relationship(
                    session,
                    site_id,
                    target_id,
                    "nearby",
                    distance_meters=candidate["distance_meters"],
                    relationship_metadata={"radius_meters": radius_meters},
                    verification_status="draft",
                )
            )
    return created
