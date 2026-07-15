from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import MediaReviewItem

PUBLIC_ROLES = {"data_manager", "system_admin"}
INTERNAL_ROLES = {"reviewer", "data_manager", "system_admin"}


def list_media_review_items(
    session: Session,
    *,
    search: str | None = None,
    feature_id: str | None = None,
    domain: str | None = None,
    source_type: str | None = None,
    review_status: str | None = None,
    rights_status: str | None = None,
    download_status: str | None = None,
    has_site_name: bool | None = None,
    limit: int = 25,
    offset: int = 0,
):
    stmt = select(MediaReviewItem)
    for column, value in (
        (MediaReviewItem.feature_id, feature_id),
        (MediaReviewItem.domain, domain),
        (MediaReviewItem.source_type, source_type),
        (MediaReviewItem.review_status, review_status),
        (MediaReviewItem.rights_status, rights_status),
        (MediaReviewItem.download_status, download_status),
    ):
        if value:
            stmt = stmt.where(column == value)
    if search:
        stmt = stmt.where(
            or_(MediaReviewItem.feature_id.ilike(f"%{search}%"), MediaReviewItem.site_name.ilike(f"%{search}%"))
        )
    if has_site_name is not None:
        stmt = stmt.where(
            MediaReviewItem.site_name.is_not(None) if has_site_name else MediaReviewItem.site_name.is_(None)
        )
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    return list(
        session.scalars(stmt.order_by(MediaReviewItem.created_at, MediaReviewItem.id).offset(offset).limit(limit))
    ), total


def get_media_review_item(session: Session, item_id: UUID):
    item = session.get(MediaReviewItem, item_id)
    if not item:
        raise LookupError(item_id)
    return item


def submit_media_review(session: Session, item_id: UUID, data: dict[str, Any], role: str):
    item = get_media_review_item(session, item_id)
    decision = data.get("review_status", item.review_status)
    rights = data.get("rights_status", item.rights_status)
    if role == "viewer":
        raise PermissionError("viewer is read-only")
    if rights == "approved_public" and role not in PUBLIC_ROLES:
        raise PermissionError("public approval requires data_manager")
    if rights == "approved_internal" and role not in INTERNAL_ROLES:
        raise PermissionError("internal approval requires reviewer")
    if rights == "approved_public" and not any(
        str(data.get(k) or getattr(item, k) or "").strip()
        for k in ("rights_owner", "rights_evidence", "reviewer_notes")
    ):
        raise ValueError("public approval requires legal basis")
    if role == "editor" and (decision != "pending_review" or rights not in {"unknown", "pending_review"}):
        raise PermissionError("editor may only add notes")
    for key in ("review_status", "rights_status", "rights_owner", "rights_evidence", "intended_use", "reviewer_notes"):
        if key in data:
            setattr(item, key, data[key])
    item.reviewer_role = role
    item.reviewed_at = datetime.now(timezone.utc)
    item.updated_at = datetime.now(timezone.utc)
    session.flush()
    return item


def bulk_review_preview(session: Session, ids: list[UUID]):
    items = list(session.scalars(select(MediaReviewItem).where(MediaReviewItem.id.in_(ids))))
    return {
        "requested": len(ids),
        "matched": len(items),
        "pending": sum(i.review_status == "pending_review" for i in items),
        "domains": dict(__import__("collections").Counter(i.domain for i in items)),
    }


def bulk_approve_internal(session: Session, ids: list[UUID], role: str, notes: str | None = None):
    return [
        submit_media_review(
            session,
            i,
            {"review_status": "approved", "rights_status": "approved_internal", "reviewer_notes": notes},
            role,
        )
        for i in ids
    ]


def bulk_reject(session: Session, ids: list[UUID], role: str, notes: str | None = None):
    return [
        submit_media_review(
            session, i, {"review_status": "rejected", "rights_status": "restricted", "reviewer_notes": notes}, role
        )
        for i in ids
    ]


def list_ready_for_download(session: Session, limit: int = 100):
    return list(
        session.scalars(
            select(MediaReviewItem)
            .where(
                MediaReviewItem.review_status == "approved",
                MediaReviewItem.rights_status.in_(("approved_internal", "approved_public")),
                MediaReviewItem.download_status == "not_requested",
            )
            .limit(limit)
        )
    )


def calculate_media_review_summary(session: Session):
    total = int(session.scalar(select(func.count()).select_from(MediaReviewItem)) or 0)
    rights = dict(
        session.execute(
            select(MediaReviewItem.rights_status, func.count()).group_by(MediaReviewItem.rights_status)
        ).all()
    )
    reviews = dict(
        session.execute(
            select(MediaReviewItem.review_status, func.count()).group_by(MediaReviewItem.review_status)
        ).all()
    )
    ready = int(
        session.scalar(
            select(func.count())
            .select_from(MediaReviewItem)
            .where(
                MediaReviewItem.review_status == "approved",
                MediaReviewItem.rights_status.in_(("approved_internal", "approved_public")),
                MediaReviewItem.download_status == "not_requested",
            )
        )
        or 0
    )
    return {
        "total": total,
        "pending": reviews.get("pending_review", 0),
        "approved_internal": rights.get("approved_internal", 0),
        "approved_public": rights.get("approved_public", 0),
        "rejected": reviews.get("rejected", 0),
        "ready_for_download": ready,
    }
