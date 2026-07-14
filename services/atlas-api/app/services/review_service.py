from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, cast, exists, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import FeatureReview, ImportFeature, PromotionRecord, Site
from app.models.tables import REVIEW_DECISIONS, REVIEW_STAGES

SORT_COLUMNS = {
    "source_feature_id": ImportFeature.source_feature_id,
    "name_ar": ImportFeature.name_ar,
    "geometry_type": ImportFeature.geometry_type,
    "review_status": ImportFeature.review_status,
    "reviewed_at": ImportFeature.reviewed_at,
}


def build_feature_query(
    *,
    geometry_type: str | None = None,
    review_status: str | None = None,
    review_stage: str | None = None,
    folder_name: str | None = None,
    has_name: bool | None = None,
    has_images: bool | None = None,
    promotion_eligible: bool | None = None,
    search: str | None = None,
) -> Select[tuple[ImportFeature]]:
    query = select(ImportFeature)
    if geometry_type:
        query = query.where(ImportFeature.geometry_type == geometry_type)
    if review_status:
        query = query.where(ImportFeature.review_status == review_status)
    if review_stage:
        query = query.where(
            exists(
                select(FeatureReview.id).where(
                    FeatureReview.import_feature_id == ImportFeature.id, FeatureReview.review_stage == review_stage
                )
            )
        )
    if folder_name:
        query = query.where(ImportFeature.properties["folder_name"].astext == folder_name)
    if has_name is not None:
        query = query.where(ImportFeature.missing_name.is_(not has_name))
    if has_images is not None:
        image_count = func.jsonb_array_length(
            func.coalesce(ImportFeature.properties["image_urls"], cast(literal("[]"), JSONB))
        )
        query = query.where(image_count > 0 if has_images else image_count == 0)
    if promotion_eligible is not None:
        query = query.where(ImportFeature.promotion_eligible.is_(promotion_eligible))
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                ImportFeature.name_ar.ilike(term),
                ImportFeature.source_feature_id.ilike(term),
                ImportFeature.properties["description_text"].astext.ilike(term),
            )
        )
    return query


def list_pending_features(
    session: Session,
    *,
    limit: int = 25,
    offset: int = 0,
    sort_by: str = "source_feature_id",
    sort_order: str = "asc",
    **filters: Any,
) -> tuple[list[ImportFeature], int]:
    query = build_feature_query(**filters)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    column = SORT_COLUMNS.get(sort_by, ImportFeature.source_feature_id)
    order = column.desc().nullslast() if sort_order == "desc" else column.asc().nullslast()
    items = list(session.scalars(query.order_by(order).limit(min(limit, 100)).offset(offset)))
    return items, total


def get_feature_review_details(session: Session, feature_id: uuid.UUID) -> tuple[ImportFeature, list[FeatureReview]]:
    feature = session.get(ImportFeature, feature_id)
    if feature is None:
        raise LookupError("سجل Staging غير موجود")
    reviews = list(
        session.scalars(
            select(FeatureReview)
            .where(FeatureReview.import_feature_id == feature_id)
            .order_by(FeatureReview.created_at)
        )
    )
    return feature, reviews


def submit_review(
    session: Session,
    feature_id: uuid.UUID,
    *,
    review_stage: str,
    decision: str,
    reviewer_role: str,
    reviewer_id: uuid.UUID | None = None,
    notes: str | None = None,
    proposed_name_ar: str | None = None,
    proposed_category_id: uuid.UUID | None = None,
    proposed_municipality_id: uuid.UUID | None = None,
) -> FeatureReview:
    if review_stage not in REVIEW_STAGES or decision not in REVIEW_DECISIONS:
        raise ValueError("مرحلة أو قرار مراجعة غير صالح")
    feature, _ = get_feature_review_details(session, feature_id)
    review = session.scalar(
        select(FeatureReview).where(
            FeatureReview.import_feature_id == feature_id, FeatureReview.review_stage == review_stage
        )
    )
    if review is None:
        review = FeatureReview(
            import_feature_id=feature_id, review_stage=review_stage, decision=decision, reviewer_role=reviewer_role
        )
        session.add(review)
    review.decision, review.reviewer_id, review.reviewer_role, review.notes = (
        decision,
        reviewer_id,
        reviewer_role,
        notes,
    )
    review.proposed_name_ar, review.proposed_category_id, review.proposed_municipality_id = (
        proposed_name_ar,
        proposed_category_id,
        proposed_municipality_id,
    )
    review.reviewed_at = datetime.now(timezone.utc)
    if proposed_name_ar:
        feature.name_ar = proposed_name_ar.strip()
        feature.missing_name = not bool(feature.name_ar)
    feature.reviewed_at = review.reviewed_at
    feature.review_status = (
        "rejected"
        if decision == "rejected"
        else "needs_correction"
        if decision == "needs_correction"
        else "pending_review"
    )
    session.flush()
    feature.promotion_eligible = calculate_promotion_eligibility(session, feature_id)["eligible"]
    return review


def calculate_promotion_eligibility(session: Session, feature_id: uuid.UUID) -> dict[str, Any]:
    feature, reviews = get_feature_review_details(session, feature_id)
    decisions = {review.review_stage: review.decision for review in reviews}
    issues = [str(issue).lower() for issue in (feature.validation_issues or [])]
    duplicate_open = any("duplicate" in issue or "تكرار" in issue for issue in issues) or bool(
        feature.properties.get("duplicate_suspected")
    )
    critical = any(
        issue.startswith("critical") or "invalid_geometry" in issue or "invalid_coordinate" in issue for issue in issues
    )
    geometry_valid = bool(session.scalar(select(func.ST_IsValid(feature.geometry))))
    national_id_duplicate = bool(
        feature.proposed_national_id
        and session.scalar(select(Site.id).where(Site.national_id == feature.proposed_national_id))
    )
    already_promoted = bool(
        session.scalar(
            select(PromotionRecord.id).where(
                PromotionRecord.import_feature_id == feature_id, PromotionRecord.status == "promoted"
            )
        )
    )
    checks = {
        "point_geometry": feature.geometry_type == "Point",
        "has_name": bool(feature.name_ar and feature.name_ar.strip()),
        "valid_geometry": geometry_valid,
        "technical_accepted": decisions.get("technical") == "accepted",
        "gis_accepted": decisions.get("gis") == "accepted",
        "data_accepted": decisions.get("data") == "accepted",
        "final_accepted": decisions.get("final") == "accepted",
        "no_critical_issues": not critical,
        "national_id_unique": not national_id_duplicate,
        "no_open_duplicate_suspicion": not duplicate_open,
        "not_already_promoted": not already_promoted,
    }
    return {"feature_id": str(feature.id), "eligible": all(checks.values()), "checks": checks}


def reject_feature(
    session: Session, feature_id: uuid.UUID, reviewer_role: str, notes: str | None = None
) -> FeatureReview:
    return submit_review(
        session, feature_id, review_stage="final", decision="rejected", reviewer_role=reviewer_role, notes=notes
    )


def request_correction(
    session: Session, feature_id: uuid.UUID, review_stage: str, reviewer_role: str, notes: str | None = None
) -> FeatureReview:
    return submit_review(
        session,
        feature_id,
        review_stage=review_stage,
        decision="needs_correction",
        reviewer_role=reviewer_role,
        notes=notes,
    )


def approve_feature(
    session: Session, feature_id: uuid.UUID, review_stage: str, reviewer_role: str, **kwargs: Any
) -> FeatureReview:
    return submit_review(
        session, feature_id, review_stage=review_stage, decision="accepted", reviewer_role=reviewer_role, **kwargs
    )
