from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.services import media_review_service as service

router = APIRouter(prefix="/api/v1/media-review", tags=["media-review"])
Role = Annotated[str, Depends(get_reviewer_role)]


def serialize(i):
    return {
        "id": str(i.id),
        "feature_id": i.feature_id,
        "site_id": str(i.site_id) if i.site_id else None,
        "site_name": i.site_name,
        "original_url": i.original_url,
        "normalized_url": i.normalized_url,
        "domain": i.domain,
        "source_type": i.source_type,
        "review_status": i.review_status,
        "rights_status": i.rights_status,
        "rights_owner": i.rights_owner,
        "rights_evidence": i.rights_evidence,
        "intended_use": i.intended_use,
        "reviewer_role": i.reviewer_role,
        "reviewer_notes": i.reviewer_notes,
        "reviewed_at": i.reviewed_at,
        "download_status": i.download_status,
        "local_media_url": i.local_media_url,
        "sha256": i.sha256,
    }


def internal(role: str):
    if role == "viewer":
        raise HTTPException(403, "الوحدة متاحة للأدوار الداخلية فقط")


@router.get("/summary")
def summary(role: Role, db: Session = Depends(get_db)):
    return service.calculate_media_review_summary(db)


@router.get("/items")
def items(
    role: Role,
    search: str | None = None,
    feature_id: str | None = None,
    domain: str | None = None,
    source_type: str | None = None,
    review_status: str | None = None,
    rights_status: str | None = None,
    download_status: str | None = None,
    has_site_name: bool | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    internal(role)
    values, total = service.list_media_review_items(
        db,
        search=search,
        feature_id=feature_id,
        domain=domain,
        source_type=source_type,
        review_status=review_status,
        rights_status=rights_status,
        download_status=download_status,
        has_site_name=has_site_name,
        limit=limit,
        offset=offset,
    )
    return {"items": [serialize(i) for i in values], "total": total, "limit": limit, "offset": offset}


@router.get("/items/{item_id}")
def item(item_id: UUID, role: Role, db: Session = Depends(get_db)):
    internal(role)
    try:
        return serialize(service.get_media_review_item(db, item_id))
    except LookupError:
        raise HTTPException(404, "مرجع الصورة غير موجود") from None


@router.post("/items/{item_id}/decision")
def decision(item_id: UUID, data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    internal(role)
    try:
        value = service.submit_media_review(db, item_id, data, role)
        db.commit()
        return serialize(value)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/bulk-preview")
def bulk_preview(data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    internal(role)
    return service.bulk_review_preview(db, [UUID(v) for v in data.get("ids", [])])


@router.post("/bulk-decision")
def bulk_decision(data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    if role not in {"data_manager", "system_admin"}:
        raise HTTPException(403, "القرار الجماعي يتطلب مدير بيانات")
    ids = [UUID(v) for v in data.get("ids", [])]
    action = data.get("action")
    try:
        values = (
            service.bulk_approve_internal(db, ids, role, data.get("notes"))
            if action == "approve_internal"
            else service.bulk_reject(db, ids, role, data.get("notes"))
        )
        db.commit()
        return {"updated": len(values)}
    except (PermissionError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/ready-for-download")
def ready(role: Role, limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)):
    internal(role)
    return {"items": [serialize(i) for i in service.list_ready_for_download(db, limit)]}
