from __future__ import annotations

import json
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.auth import ensure_promotion_permission, ensure_review_permission, get_reviewer_role
from app.api.deps import get_db
from app.models import AuditLog, ImportFeature, PromotionRecord
from app.schemas.review import BulkPromotePreviewRequest, PromoteRequest, ReviewDecisionRequest
from app.services.data_quality_service import calculate_quality
from app.services.promotion_service import PromotionNotAllowedError, promote_feature
from app.services.review_service import (
    calculate_promotion_eligibility,
    get_feature_review_details,
    list_pending_features,
    submit_review,
)

router = APIRouter(prefix="/api/v1/review", tags=["government-review"])
Role = Annotated[str, Depends(get_reviewer_role)]


def compact_feature(session: Session, feature: ImportFeature) -> dict[str, object]:
    properties = feature.properties or {}
    quality = calculate_quality(session, feature)
    return {
        "id": str(feature.id),
        "source_feature_id": feature.source_feature_id,
        "name_ar": feature.name_ar,
        "geometry_type": feature.geometry_type,
        "review_status": feature.review_status,
        "folder_name": properties.get("folder_name"),
        "image_count": len(properties.get("image_urls") or []),
        "promotion_eligible": feature.promotion_eligible,
        "quality_score": quality["quality_score"],
    }


@router.get("/summary")
def review_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    def count(*where: object) -> int:
        return int(db.scalar(select(func.count()).select_from(ImportFeature).where(*where)) or 0)

    promoted = int(
        db.scalar(select(func.count()).select_from(PromotionRecord).where(PromotionRecord.status == "promoted")) or 0
    )
    return {
        "total_features": count(),
        "pending_review": count(ImportFeature.review_status == "pending_review"),
        "accepted": count(ImportFeature.review_status == "accepted"),
        "rejected": count(ImportFeature.review_status == "rejected"),
        "needs_correction": count(ImportFeature.review_status == "needs_correction"),
        "eligible_for_promotion": count(ImportFeature.promotion_eligible.is_(True)),
        "promoted": promoted,
        "points": count(ImportFeature.geometry_type == "Point"),
        "lines": count(ImportFeature.geometry_type == "LineString"),
        "polygons": count(ImportFeature.geometry_type == "Polygon"),
        "named_features": count(ImportFeature.missing_name.is_(False)),
        "unnamed_features": count(ImportFeature.missing_name.is_(True)),
    }


@router.get("/features")
def features(
    geometry_type: str | None = None,
    review_status: str | None = None,
    review_stage: str | None = None,
    has_name: bool | None = None,
    has_images: bool | None = None,
    promotion_eligible: bool | None = None,
    folder_name: str | None = None,
    search: str | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("source_feature_id"),
    sort_order: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items, total = list_pending_features(
        db,
        geometry_type=geometry_type,
        review_status=review_status,
        review_stage=review_stage,
        has_name=has_name,
        has_images=has_images,
        promotion_eligible=promotion_eligible,
        folder_name=folder_name,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {"items": [compact_feature(db, item) for item in items], "total": total, "limit": limit, "offset": offset}


@router.get("/features/{feature_id}")
def feature_details(feature_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        feature, reviews = get_feature_review_details(db, feature_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    properties = feature.properties or {}
    geometry_text = db.scalar(select(func.ST_AsGeoJSON(feature.geometry)))
    promotion = db.scalar(select(PromotionRecord).where(PromotionRecord.import_feature_id == feature_id))
    audit_conditions = [cast(AuditLog.details["import_feature_id"].astext, String) == str(feature_id)]
    if promotion and promotion.site_id:
        audit_conditions.append(AuditLog.entity_id == promotion.site_id)
    audit_query = select(AuditLog).where(or_(*audit_conditions)).order_by(AuditLog.created_at)
    audits = list(db.scalars(audit_query))
    return {
        **compact_feature(db, feature),
        "geometry": json.loads(geometry_text) if geometry_text else None,
        "properties": properties,
        "images": properties.get("image_urls") or [],
        "description_html": properties.get("description_html"),
        "description_text": properties.get("description_text"),
        "extended_data": properties.get("extended_data") or {},
        "validation_issues": feature.validation_issues or [],
        "reviews": [
            {
                "id": str(review.id),
                "review_stage": review.review_stage,
                "decision": review.decision,
                "reviewer_role": review.reviewer_role,
                "notes": review.notes,
                "proposed_name_ar": review.proposed_name_ar,
                "reviewed_at": review.reviewed_at,
            }
            for review in reviews
        ],
        "eligibility": calculate_promotion_eligibility(db, feature_id),
        "quality": calculate_quality(db, feature),
        "promotion_record": None
        if promotion is None
        else {
            "id": str(promotion.id),
            "site_id": str(promotion.site_id) if promotion.site_id else None,
            "status": promotion.status,
            "promoted_at": promotion.promoted_at,
            "failure_reason": promotion.failure_reason,
        },
        "audit_timeline": [
            {"id": str(item.id), "action": item.action, "details": item.details, "created_at": item.created_at}
            for item in audits
        ],
    }


@router.post("/features/{feature_id}/reviews")
def create_review(
    feature_id: uuid.UUID, payload: ReviewDecisionRequest, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    ensure_review_permission(role, payload.review_stage, payload.decision)
    if payload.reviewer_role != role:
        raise HTTPException(403, "دور جسم الطلب لا يطابق ترويسة المراجع")
    try:
        review = submit_review(db, feature_id, **payload.model_dump())
        db.commit()
        return {
            "id": str(review.id),
            "review_stage": review.review_stage,
            "decision": review.decision,
            "promotion_eligible": calculate_promotion_eligibility(db, feature_id)["eligible"],
        }
    except (LookupError, ValueError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc


@router.post("/features/{feature_id}/decision", include_in_schema=False)
def legacy_decision(
    feature_id: uuid.UUID, payload: ReviewDecisionRequest, role: Role, db: Session = Depends(get_db)
) -> dict[str, object]:
    return create_review(feature_id, payload, role, db)


@router.get("/features/{feature_id}/eligibility")
def eligibility(feature_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return calculate_promotion_eligibility(db, feature_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/features/{feature_id}/promote")
def promote(
    feature_id: uuid.UUID, payload: PromoteRequest, role: Role, db: Session = Depends(get_db)
) -> dict[str, str]:
    ensure_promotion_permission(role)
    try:
        site = promote_feature(db, feature_id, promoted_by=payload.promoted_by)
        db.commit()
        return {"site_id": str(site.id), "national_id": site.national_id, "status": "promoted"}
    except (LookupError, PromotionNotAllowedError) as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc


@router.get("/features/{feature_id}/duplicate-candidates")
def duplicate_candidates(
    feature_id: uuid.UUID, limit: int = Query(10, ge=1, le=25), db: Session = Depends(get_db)
) -> dict[str, object]:
    feature = db.get(ImportFeature, feature_id)
    if feature is None:
        raise HTTPException(404, "السجل غير موجود")
    if feature.geometry_type != "Point":
        return {"feature_id": str(feature_id), "items": []}
    name_similarity = func.similarity(func.coalesce(ImportFeature.name_ar, ""), feature.name_ar or "")
    distance = func.ST_DistanceSphere(ImportFeature.geometry, feature.geometry)
    query = (
        select(ImportFeature, name_similarity.label("name_similarity"), distance.label("distance_meters"))
        .where(
            ImportFeature.id != feature_id,
            ImportFeature.geometry_type == "Point",
            or_(name_similarity >= 0.25, distance <= 500),
        )
        .order_by(name_similarity.desc(), distance.asc())
        .limit(limit)
    )
    items = []
    source_category = feature.proposed_category_code or (feature.properties.get("extended_data") or {}).get("النوع")
    for candidate, similarity, meters in db.execute(query):
        candidate_category = candidate.proposed_category_code or (candidate.properties.get("extended_data") or {}).get(
            "النوع"
        )
        category_match = bool(source_category and source_category == candidate_category)
        distance_score = max(0.0, 1.0 - float(meters or 0) / 500.0)
        confidence = round(
            min(1.0, float(similarity or 0) * 0.6 + distance_score * 0.3 + (0.1 if category_match else 0)), 3
        )
        items.append(
            {
                "id": str(candidate.id),
                "source_feature_id": candidate.source_feature_id,
                "name_ar": candidate.name_ar,
                "name_similarity": round(float(similarity or 0), 3),
                "distance_meters": round(float(meters or 0), 1),
                "category_match": category_match,
                "confidence_score": confidence,
            }
        )
    return {"feature_id": str(feature_id), "items": items}


@router.post("/bulk-promote-preview")
def bulk_preview(payload: BulkPromotePreviewRequest, role: Role, db: Session = Depends(get_db)) -> dict[str, object]:
    ensure_promotion_permission(role)
    results = [calculate_promotion_eligibility(db, feature_id) for feature_id in payload.feature_ids]
    return {
        "total": len(results),
        "eligible": sum(bool(item["eligible"]) for item in results),
        "items": results,
        "preview_only": True,
    }
