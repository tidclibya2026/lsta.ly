from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import ensure_registry_admin, ensure_registry_edit, get_reviewer_role
from app.api.deps import get_db
from app.models import AuditLog, ImportFeature, PublicationRecord, Site, SiteGeometry, SiteProfile, SiteRelationship
from app.schemas.registry import (
    AttributeUpdate,
    DocumentCreate,
    NearbyRefresh,
    ProfileUpdate,
    RelationshipCreate,
    RelationshipReview,
    SiteUpdate,
)
from app.services.registry_service import (
    archive_registry_site,
    get_registry_site,
    list_registry_sites,
    restore_registry_site,
    update_registry_site,
)
from app.services.site_completeness_service import calculate_site_completeness
from app.services.site_profile_service import (
    create_document_metadata,
    create_or_update_profile,
    delete_attribute,
    delete_document_metadata,
    get_profile,
    list_attributes,
    list_documents,
    list_media,
    upsert_attribute,
)
from app.services.site_quality_snapshot_service import list_quality_snapshots
from app.services.site_version_service import create_version_snapshot, get_version, list_versions
from app.services.spatial_relationship_service import (
    create_manual_relationship,
    delete_relationship,
    list_site_relationships,
    refresh_nearby_relationships,
    reject_relationship,
    relationship_summary,
    timed_nearby_query,
    verify_relationship,
)

router = APIRouter(prefix="/api/v1/registry", tags=["national-registry"])
Role = Annotated[str, Depends(get_reviewer_role)]


def latest_publication(session: Session, site_id: uuid.UUID) -> str:
    return (
        session.scalar(
            select(PublicationRecord.publication_status)
            .where(PublicationRecord.site_id == site_id)
            .order_by(PublicationRecord.published_at.desc().nullslast())
            .limit(1)
        )
        or "internal"
    )


def site_item(session: Session, site: Site) -> dict[str, object]:
    completeness = calculate_site_completeness(session, site)
    return {
        "id": str(site.id),
        "national_id": site.national_id,
        "slug": site.slug,
        "name_ar": site.name_ar,
        "name_en": site.name_en,
        "verification_status": site.verification_status,
        "publication_status": latest_publication(session, site.id),
        "profile_completeness_score": completeness["score"],
    }


@router.get("/summary")
def summary(db: Session = Depends(get_db)) -> dict[str, float | int]:
    sites = list(db.scalars(select(Site)))
    scores = [calculate_site_completeness(db, site)["score"] for site in sites]
    return {
        "total_sites": len(sites),
        "approved": sum(site.verification_status == "approved" for site in sites),
        "internal": sum(latest_publication(db, site.id) == "internal" for site in sites),
        "archived": sum(site.verification_status == "archived" for site in sites),
        "average_completeness": round(sum(scores) / len(scores), 2) if scores else 0,
    }


@router.get("/sites")
def sites(
    search: str | None = None,
    category: str | None = None,
    municipality: str | None = None,
    verification_status: str | None = None,
    publication_status: str | None = None,
    completeness_min: float | None = Query(None, ge=0, le=100),
    completeness_max: float | None = Query(None, ge=0, le=100),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items, total = list_registry_sites(
        db,
        search=search,
        category=category,
        municipality=municipality,
        verification_status=verification_status,
        publication_status=publication_status,
        completeness_min=completeness_min,
        completeness_max=completeness_max,
        limit=limit,
        offset=offset,
    )
    return {"items": [site_item(db, site) for site in items], "total": total, "limit": limit, "offset": offset}


@router.get("/sites/{national_id}")
def site_details(national_id: str, role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        site = get_registry_site(db, national_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    profile = get_profile(db, site.id, create=True)
    db.commit()
    geometry_text = db.scalar(
        select(func.ST_AsGeoJSON(SiteGeometry.geometry))
        .where(SiteGeometry.site_id == site.id)
        .order_by(SiteGeometry.id)
        .limit(1)
    )
    result = site_item(db, site)
    result.update(
        {
            "description": site.description,
            "category_id": str(site.category_id) if site.category_id else None,
            "municipality_id": str(site.municipality_id) if site.municipality_id else None,
            "geometry": json.loads(geometry_text) if geometry_text else None,
            "profile": profile_dict(profile, include_internal=role in {"system_admin", "data_manager"}),
            "completeness": calculate_site_completeness(db, site),
            "audit_timeline": [
                {"id": str(item.id), "action": item.action, "details": item.details, "created_at": item.created_at}
                for item in db.scalars(
                    select(AuditLog).where(AuditLog.entity_id == site.id).order_by(AuditLog.created_at.desc())
                )
            ],
        }
    )
    return result


def profile_dict(profile: SiteProfile | None, *, include_internal: bool) -> dict[str, object] | None:
    if profile is None:
        return None
    values = {
        column.name: getattr(profile, column.name)
        for column in SiteProfile.__table__.columns
        if column.name not in {"site_id"}
    }
    values["id"] = str(profile.id)
    if not include_internal:
        values.pop("internal_notes", None)
    return values


def audit(db: Session, site: Site, action: str, role: str, details: dict[str, object] | None = None) -> None:
    db.add(
        AuditLog(
            action=action,
            entity_type="site",
            entity_id=site.id,
            details={"national_id": site.national_id, "role": role, **(details or {})},
        )
    )


@router.patch("/sites/{national_id}")
def patch_site(national_id: str, payload: SiteUpdate, role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    ensure_registry_edit(role)
    site = get_registry_site(db, national_id)
    update_registry_site(db, site, payload.model_dump(exclude_unset=True), role=role)
    db.commit()
    return site_item(db, site)


@router.post("/sites/{national_id}/archive")
def archive(national_id: str, role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    ensure_registry_admin(role)
    site = archive_registry_site(db, get_registry_site(db, national_id), role)
    db.commit()
    return site_item(db, site)


@router.post("/sites/{national_id}/restore")
def restore(national_id: str, role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    ensure_registry_admin(role)
    site = restore_registry_site(db, get_registry_site(db, national_id), role)
    db.commit()
    return site_item(db, site)


@router.get("/sites/{national_id}/profile")
def profile(national_id: str, role: Role, db: Session = Depends(get_db)) -> dict[str, object] | None:
    site = get_registry_site(db, national_id)
    item = get_profile(db, site.id, create=True)
    db.commit()
    return profile_dict(item, include_internal=role in {"system_admin", "data_manager"})


@router.put("/sites/{national_id}/profile")
def put_profile(
    national_id: str, payload: ProfileUpdate, role: Role, db: Session = Depends(get_db)
) -> dict[str, object] | None:
    ensure_registry_edit(role)
    site = get_registry_site(db, national_id)
    create_version_snapshot(db, site, "قبل تحديث الملف الوطني")
    values = payload.model_dump(mode="json")
    if role not in {"system_admin", "data_manager"}:
        values.pop("internal_notes", None)
    item = create_or_update_profile(db, site.id, values)
    calculate_site_completeness(db, site, persist=True)
    audit(db, site, "site_profile_updated", role)
    db.commit()
    return profile_dict(item, include_internal=role in {"system_admin", "data_manager"})


@router.get("/sites/{national_id}/attributes")
def attributes(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [
        {column.name: getattr(item, column.name) for column in item.__table__.columns}
        for item in list_attributes(db, site.id)
    ]


@router.put("/sites/{national_id}/attributes/{attribute_key}")
def put_attribute(
    national_id: str, attribute_key: str, payload: AttributeUpdate, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    ensure_registry_edit(role)
    site = get_registry_site(db, national_id)
    create_version_snapshot(db, site, f"قبل تحديث الخاصية {attribute_key}")
    item = upsert_attribute(db, site.id, attribute_key, payload.model_dump(mode="json"))
    audit(db, site, "site_attribute_upserted", role, {"attribute_key": attribute_key})
    db.commit()
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


@router.delete("/sites/{national_id}/attributes/{attribute_key}", status_code=204)
def remove_attribute(national_id: str, attribute_key: str, role: Role, db: Session = Depends(get_db)) -> None:
    ensure_registry_edit(role)
    site = get_registry_site(db, national_id)
    create_version_snapshot(db, site, f"قبل حذف الخاصية {attribute_key}")
    delete_attribute(db, site.id, attribute_key)
    audit(db, site, "site_attribute_deleted", role, {"attribute_key": attribute_key})
    db.commit()


@router.get("/sites/{national_id}/media")
def media(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [
        {column.name: getattr(item, column.name) for column in item.__table__.columns}
        for item in list_media(db, site.id)
    ]


@router.get("/sites/{national_id}/documents")
def documents(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [
        {column.name: getattr(item, column.name) for column in item.__table__.columns}
        for item in list_documents(db, site.id)
    ]


@router.post("/sites/{national_id}/documents")
def create_document(
    national_id: str, payload: DocumentCreate, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    ensure_registry_edit(role)
    site = get_registry_site(db, national_id)
    create_version_snapshot(db, site, "قبل إضافة وثيقة")
    item = create_document_metadata(db, site.id, payload.model_dump(mode="json"))
    audit(db, site, "site_document_created", role, {"file_name": item.file_name})
    db.commit()
    return {"id": str(item.id), "title_ar": item.title_ar, "document_type": item.document_type}


@router.delete("/sites/{national_id}/documents/{document_id}", status_code=204)
def remove_document(national_id: str, document_id: uuid.UUID, role: Role, db: Session = Depends(get_db)) -> None:
    ensure_registry_admin(role)
    site = get_registry_site(db, national_id)
    create_version_snapshot(db, site, "قبل حذف بيانات وثيقة")
    delete_document_metadata(db, site.id, document_id)
    audit(db, site, "site_document_deleted", role, {"document_id": str(document_id)})
    db.commit()


@router.get("/sites/{national_id}/relationships")
def relationships(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [relationship_item(db, item) for item in list_site_relationships(db, site.id)]


def relationship_item(db: Session, item: SiteRelationship) -> dict[str, object]:
    if item.target_site_id:
        target = db.get(Site, item.target_site_id)
        target_type, target_id, target_name, geometry_type = (
            "registry",
            str(item.target_site_id),
            target.name_ar if target else None,
            None,
        )
        if target:
            geometry_type = db.scalar(
                select(SiteGeometry.geometry_type).where(SiteGeometry.site_id == target.id).limit(1)
            )
    else:
        feature = db.get(ImportFeature, item.target_staging_feature_id)
        target_type, target_id = "staging", str(item.target_staging_feature_id)
        target_name, geometry_type = (feature.name_ar, feature.geometry_type) if feature else (None, None)
    return {
        "relationship_id": str(item.id),
        "relationship_type": item.relationship_type,
        "source_method": item.source_method,
        "verification_status": item.verification_status,
        "target_type": target_type,
        "target_id": target_id,
        "target_name": target_name,
        "geometry_type": geometry_type,
        "distance_meters": float(item.distance_meters) if item.distance_meters is not None else None,
        "confidence_score": float(item.confidence_score) if item.confidence_score is not None else None,
        "created_at": item.created_at,
        "verified_at": item.verified_at,
    }


@router.post("/sites/{national_id}/relationships")
def post_relationship(
    national_id: str, payload: RelationshipCreate, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    if role not in {"editor", "gis_specialist", "data_manager", "system_admin"}:
        raise HTTPException(403, "لا توجد صلاحية لإنشاء العلاقة")
    site = get_registry_site(db, national_id)
    values: dict[str, object] = {
        "relationship_type": payload.relationship_type,
        "distance_meters": payload.distance_meters,
        "metadata": payload.relationship_metadata,
    }
    if payload.target_type == "registry":
        values["target_site_id"] = get_registry_site(db, payload.target_id).id
    else:
        try:
            values["target_staging_feature_id"] = uuid.UUID(payload.target_id)
        except ValueError as exc:
            raise HTTPException(400, "معرف Staging غير صالح") from exc
        if db.get(ImportFeature, values["target_staging_feature_id"]) is None:
            raise HTTPException(404, "عنصر Staging غير موجود")
    try:
        item = create_manual_relationship(db, site.id, **values)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    audit(
        db,
        site,
        "site_relationship_created",
        role,
        {"target_type": payload.target_type, "target_id": payload.target_id},
    )
    db.commit()
    return relationship_item(db, item)


@router.delete("/sites/{national_id}/relationships/{relationship_id}", status_code=204)
def remove_relationship(
    national_id: str, relationship_id: uuid.UUID, role: Role, db: Session = Depends(get_db)
) -> None:
    ensure_registry_admin(role)
    site = get_registry_site(db, national_id)
    delete_relationship(db, site.id, relationship_id)
    audit(db, site, "site_relationship_deleted", role)
    db.commit()


@router.get("/sites/{national_id}/nearby")
def nearby(
    national_id: str,
    radius_meters: float = Query(2000, gt=0, le=100000),
    source: str = Query("staging", pattern="^(registry|staging|all)$"),
    geometry_type: str | None = None,
    has_name: bool | None = None,
    category: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    site = get_registry_site(db, national_id)
    return timed_nearby_query(
        db,
        site,
        radius_meters=radius_meters,
        source=source,
        geometry_type=geometry_type,
        has_name=has_name,
        category=category,
        limit=limit,
    )


@router.post("/sites/{national_id}/relationships/refresh")
def refresh_nearby(
    national_id: str, payload: NearbyRefresh, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    if role not in {"gis_specialist", "data_manager", "system_admin"}:
        raise HTTPException(403, "تحديث العلاقات المكانية مخصص لاختصاصي GIS")
    site = get_registry_site(db, national_id)
    items = refresh_nearby_relationships(
        db,
        site,
        radius_meters=payload.radius_meters,
        relationship_type=payload.relationship_type,
        source=payload.source,
        limit=payload.limit,
    )
    db.commit()
    return {"created": len(items), "items": [relationship_item(db, item) for item in items]}


def review_relationship(
    national_id: str, relationship_id: uuid.UUID, payload: RelationshipReview, role: str, decision: str, db: Session
) -> dict[str, object]:
    site = get_registry_site(db, national_id)
    item = db.get(SiteRelationship, relationship_id)
    if item is None or item.source_site_id != site.id:
        raise HTTPException(404, "العلاقة غير موجودة")
    allowed = (
        role in {"data_manager", "system_admin"}
        or (item.source_method == "spatial_query" and role == "gis_specialist")
        or (item.source_method != "spatial_query" and role == "reviewer")
    )
    if not allowed:
        raise HTTPException(403, "لا توجد صلاحية لمراجعة هذه العلاقة")
    reviewed = (
        verify_relationship(db, site.id, relationship_id, payload.verified_by)
        if decision == "verify"
        else reject_relationship(db, site.id, relationship_id, payload.verified_by)
    )
    audit(db, site, f"site_relationship_{decision}", role, {"relationship_id": str(relationship_id)})
    db.commit()
    return relationship_item(db, reviewed)


@router.post("/sites/{national_id}/relationships/{relationship_id}/verify")
def verify_relation(
    national_id: str, relationship_id: uuid.UUID, payload: RelationshipReview, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    return review_relationship(national_id, relationship_id, payload, role, "verify", db)


@router.post("/sites/{national_id}/relationships/{relationship_id}/reject")
def reject_relation(
    national_id: str, relationship_id: uuid.UUID, payload: RelationshipReview, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    return review_relationship(national_id, relationship_id, payload, role, "reject", db)


@router.get("/sites/{national_id}/relationships/summary")
def relationships_summary(national_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return relationship_summary(db, get_registry_site(db, national_id).id)


@router.get("/sites/{national_id}/versions")
def versions(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [
        {"version_number": item.version_number, "change_summary": item.change_summary, "created_at": item.created_at}
        for item in list_versions(db, site.id)
    ]


@router.get("/sites/{national_id}/versions/{version_number}")
def version(national_id: str, version_number: int, db: Session = Depends(get_db)) -> dict[str, object]:
    site = get_registry_site(db, national_id)
    item = get_version(db, site.id, version_number)
    return {
        "version_number": item.version_number,
        "snapshot": item.snapshot,
        "change_summary": item.change_summary,
        "created_at": item.created_at,
    }


@router.get("/sites/{national_id}/completeness")
def completeness(national_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return calculate_site_completeness(db, get_registry_site(db, national_id))


@router.get("/sites/{national_id}/quality-snapshots")
def quality_snapshots(national_id: str, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    site = get_registry_site(db, national_id)
    return [
        {
            "id": str(item.id),
            "overall_score": float(item.overall_score),
            "score_breakdown": item.score_breakdown,
            "critical_issues": item.critical_issues,
            "warnings": item.warnings,
            "calculated_at": item.calculated_at,
            "calculated_by": item.calculated_by,
            "source_version": item.source_version,
        }
        for item in list_quality_snapshots(db, site.id)
    ]


@router.get("/sites/{national_id}/qr")
def qr_payload(national_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    site = get_registry_site(db, national_id)
    return {
        "national_id": site.national_id,
        "canonical_path": f"/sites/{site.national_id}",
        "future_public_url": f"https://atlas.lsta.ly/sites/{site.national_id}",
    }
