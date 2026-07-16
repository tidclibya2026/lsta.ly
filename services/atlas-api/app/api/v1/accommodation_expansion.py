from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models.tables import MergeExecutionBatch
from app.services.accommodation_expansion_selection_service import (
    calculate_expansion_safety_score,
    list_expansion_candidates,
    select_twenty_hotels,
)
from app.services.accommodation_expansion_verification_service import generate_expansion_report
from app.services.merge_rollback_service import preview_rollback
from app.services.pilot_release_gate_service import evaluate_release_gate

router = APIRouter(prefix="/api/v1/accommodation-expansion", tags=["accommodation-expansion"])


def _read(role):
    if role == "viewer":
        return
    if role not in {
        "technical_reviewer",
        "gis_specialist",
        "data_reviewer",
        "data_manager",
        "system_admin",
        "decision_maker",
        "reviewer",
    }:
        raise HTTPException(403, "role not allowed")


def _latest(db):
    return db.scalar(
        select(MergeExecutionBatch)
        .where(MergeExecutionBatch.requested_proposal_count == 20)
        .order_by(MergeExecutionBatch.created_at.desc())
    )


@router.get("/candidates")
def candidates(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    _read(role)
    return [
        {
            "proposal_id": str(p.id),
            "name": p.excel_name,
            "safety_score": calculate_expansion_safety_score(p),
            "longitude": p.kml_snapshot.get("longitude"),
            "latitude": p.kml_snapshot.get("latitude"),
        }
        for p in list_expansion_candidates(db)[:100]
    ]


@router.post("/select")
def select_sample(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    if role not in {"data_manager", "system_admin"}:
        raise HTTPException(403, "selection requires data manager")
    if _latest(db):
        raise HTTPException(409, "expansion batch already exists")
    return [
        {"proposal_id": str(p.id), "name": p.excel_name, "safety_score": calculate_expansion_safety_score(p)}
        for p in select_twenty_hotels(db)
    ]


@router.get("/selection")
def selection(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    return candidates(role, db)[:20]


@router.get("/summary")
def summary(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    b = _latest(db)
    return {
        "selected": 20 if b else 0,
        "status": b.status if b else "not_started",
        "eligible": b.eligible_proposal_count if b else 0,
        "completed": b.executed_proposal_count if b else 0,
        "failed": b.failed_proposal_count if b else 0,
        "release_gate": evaluate_release_gate()["decision"],
    }


@router.get("/execution-batch")
def execution_batch(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    b = _latest(db)
    return (
        None
        if not b
        else {
            "id": str(b.id),
            "status": b.status,
            "items": len(b.items),
            "dry_run": b.dry_run_report,
            "validation": b.validation_summary,
        }
    )


@router.get("/verification")
def verification(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    b = _latest(db)
    return [] if not b else generate_expansion_report(db, b.items)


@router.get("/report")
def report(role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    return {"summary": summary(role, db), "verification": verification(role, db)}


@router.get("/readiness")
def readiness(role=Depends(get_reviewer_role)):
    return evaluate_release_gate()


@router.post("/rollback-preview/{item_id}")
def rollback(item_id: str, role=Depends(get_reviewer_role), db: Session = Depends(get_db)):
    b = _latest(db)
    item = next((x for x in b.items if str(x.id) == item_id), None) if b else None
    if not item:
        raise HTTPException(404, "execution item not found")
    return preview_rollback(item)
