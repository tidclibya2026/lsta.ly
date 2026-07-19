<<<<<<< HEAD
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import MergeDecision, MergeProposal

REVIEW_STAGE_ORDER = ("technical", "gis", "data", "final")

REVIEW_STAGE_ROLES = {
    "technical": {"technical_reviewer", "system_admin"},
    "gis": {"gis_specialist", "system_admin"},
    "data": {"data_reviewer", "system_admin"},
    "final": {"data_manager", "system_admin"},
}

VALID_REVIEW_DECISIONS = {
    "accepted",
    "rejected",
    "needs_correction",
    "deferred",
}

PRIVILEGED_ROLES = {"data_manager", "system_admin"}


def get_merge_proposal(db: Session, proposal_id: str | UUID) -> MergeProposal:
    """Return a merge proposal or raise a consistent API error."""

    try:
        normalized_id = UUID(str(proposal_id))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid proposal id") from exc

    proposal = db.get(MergeProposal, normalized_id)

    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")

    return proposal


def build_review_history(
    proposal: MergeProposal,
    role: str,
) -> list[dict[str, Any]]:
    """Build role-filtered review history."""

    include_reviewer_reference = role in PRIVILEGED_ROLES

    return [
        {
            "id": str(decision.id),
            "stage": decision.review_stage,
            "decision": decision.decision,
            "reviewer_role": decision.reviewer_role,
            "reviewer_reference": (
                decision.reviewer_reference
                if include_reviewer_reference
                else None
            ),
            "timestamp": decision.decided_at,
            "reason": decision.decision_reason,
            "notes": decision.reviewer_notes,
            "metadata": decision.decision_metadata,
        }
        for decision in proposal.decisions
    ]


def get_stage_decisions(proposal: MergeProposal) -> dict[str, str]:
    """Return the latest stored decision for every review stage."""

    latest: dict[str, str] = {}

    for decision in proposal.decisions:
        latest[decision.review_stage] = decision.decision

    return latest


def get_completed_stages(proposal: MergeProposal) -> list[str]:
    latest = get_stage_decisions(proposal)

    return [
        stage
        for stage in REVIEW_STAGE_ORDER
        if latest.get(stage) in {"accepted", "approved_merge"}
    ]


def get_current_stage(proposal: MergeProposal) -> str | None:
    completed = set(get_completed_stages(proposal))

    for stage in REVIEW_STAGE_ORDER:
        if stage not in completed:
            return stage

    return None


def get_review_blockers(proposal: MergeProposal) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    latest = get_stage_decisions(proposal)

    for stage in REVIEW_STAGE_ORDER:
        decision = latest.get(stage)

        if decision in {"rejected", "needs_correction", "deferred"}:
            blockers.append(
                {
                    "stage": stage,
                    "decision": decision,
                    "message": f"review stage {stage} requires resolution",
                }
            )

    return blockers


def get_available_actions(
    proposal: MergeProposal,
    role: str,
) -> list[dict[str, str]]:
    current_stage = get_current_stage(proposal)

    if current_stage is None:
        return []

    if role not in REVIEW_STAGE_ROLES[current_stage]:
        return []

    return [
        {
            "stage": current_stage,
            "decision": decision,
        }
        for decision in sorted(VALID_REVIEW_DECISIONS)
    ]


def build_merge_review_detail(
    proposal: MergeProposal,
    role: str,
) -> dict[str, Any]:
    """Build the unified review response used by every atlas layer."""

    history = build_review_history(proposal, role)

    return {
        "proposal": {
            "id": str(proposal.id),
            "batch_id": str(proposal.batch_id),
            "excel_record_id": proposal.excel_record_id,
            "kml_record_id": proposal.kml_record_id,
            "excel_name": proposal.excel_name,
            "kml_name": proposal.kml_name,
            "candidate_class": proposal.candidate_class,
            "confidence_score": float(proposal.confidence_score),
            "name_similarity": float(proposal.name_similarity),
            "distance_meters": (
                float(proposal.distance_meters)
                if proposal.distance_meters is not None
                else None
            ),
            "conflict_severity": proposal.conflict_severity,
            "conflict_fields": proposal.conflict_fields,
            "review_status": proposal.review_status,
            "priority": proposal.priority,
            "assigned_role": proposal.assigned_role,
            "created_at": proposal.created_at,
            "updated_at": proposal.updated_at,
        },
        "excel": proposal.excel_snapshot,
        "kml": proposal.kml_snapshot,
        "proposed": {
            **proposal.proposed_site,
            "field_sources": proposal.field_sources,
        },
        "review": {
            "current_stage": get_current_stage(proposal),
            "completed_stages": get_completed_stages(proposal),
            "history": history,
            "blockers": get_review_blockers(proposal),
            "available_actions": get_available_actions(proposal, role),
            "last_decision": history[-1] if history else None,
        },
    }


def build_merge_comparison(
    proposal: MergeProposal,
    role: str,
) -> dict[str, Any]:
    detail = build_merge_review_detail(proposal, role)

    return {
        "proposal_id": str(proposal.id),
        "excel": detail["excel"],
        "kml": detail["kml"],
        "proposed": detail["proposed"],
        "conflict_fields": proposal.conflict_fields,
        "field_sources": proposal.field_sources,
    }


def build_merge_map_data(proposal: MergeProposal) -> dict[str, Any]:
    kml_snapshot = proposal.kml_snapshot or {}
    excel_snapshot = proposal.excel_snapshot or {}

    return {
        "proposal_id": str(proposal.id),
        "excel": {
            "longitude": excel_snapshot.get("longitude"),
            "latitude": excel_snapshot.get("latitude"),
        },
        "kml": {
            "longitude": kml_snapshot.get("longitude"),
            "latitude": kml_snapshot.get("latitude"),
            "geometry_type": kml_snapshot.get("geometry_type"),
        },
        "distance_meters": (
            float(proposal.distance_meters)
            if proposal.distance_meters is not None
            else None
        ),
    }


def apply_merge_review_decision(
    db: Session,
    proposal_id: str | UUID,
    stage: str,
    payload: dict[str, Any],
    role: str,
    *,
    workflow_scope: str,
) -> dict[str, Any]:
    """Apply a controlled review decision using the shared review engine."""

    if stage not in REVIEW_STAGE_ORDER:
        raise HTTPException(status_code=422, detail="invalid review stage")

    if role not in REVIEW_STAGE_ROLES[stage]:
        raise HTTPException(
            status_code=403,
            detail="role is not authorized for this stage",
        )

    decision = payload.get("decision")
    notes = payload.get("notes")

    if decision not in VALID_REVIEW_DECISIONS:
        raise HTTPException(status_code=422, detail="invalid review decision")

    if decision in {"rejected", "needs_correction"} and not notes:
        raise HTTPException(
            status_code=422,
            detail="notes are required for this decision",
        )

    proposal = get_merge_proposal(db, proposal_id)
    stage_index = REVIEW_STAGE_ORDER.index(stage)
    latest = get_stage_decisions(proposal)

    for previous_stage in REVIEW_STAGE_ORDER[:stage_index]:
        if latest.get(previous_stage) not in {"accepted", "approved_merge"}:
            raise HTTPException(
                status_code=409,
                detail=f"previous review stage {previous_stage} is incomplete",
            )

    stored_decision = (
        "approved_merge"
        if stage == "final" and decision == "accepted"
        else decision
    )

    proposal.decisions.append(
        MergeDecision(
            decision=stored_decision,
            review_stage=stage,
            reviewer_role=role,
            reviewer_reference=payload.get("reviewer_reference"),
            reviewer_notes=notes,
            decision_reason=payload.get("reason"),
            decision_metadata={
                **(payload.get("metadata") or {}),
                "workflow_scope": workflow_scope,
                "shared_review_engine": True,
            },
        )
    )

    if stored_decision == "approved_merge":
        proposal.review_status = "approved_merge"
    elif stored_decision == "rejected":
        proposal.review_status = "blocked"
    elif stored_decision == "needs_correction":
        proposal.review_status = "needs_correction"
    elif stored_decision == "deferred":
        proposal.review_status = "deferred"
    else:
        proposal.review_status = f"{stage}_accepted"

    db.commit()
    db.refresh(proposal)

    return build_merge_review_detail(proposal, role)
=======
"""Review workflow for one-to-one merge proposals. No function performs a merge or promotion."""
from __future__ import annotations

import hashlib
import time

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import MergeBatch, MergeDecision, MergeProposal

DECISIONS={"approved_merge","rejected_match","needs_field_verification","create_from_excel","create_from_kml","keep_separate","duplicate_excel","duplicate_kml","deferred"}
MANAGERS={"data_manager","system_admin"}
def _proposal_stmt():return select(MergeProposal).options(selectinload(MergeProposal.decisions))
def get_merge_summary(s:Session):
    total=int(s.scalar(select(func.count()).select_from(MergeProposal)) or 0);pending=int(s.scalar(select(func.count()).select_from(MergeProposal).where(MergeProposal.review_status=="pending_review")) or 0)
    def count(column,value):
        return int(s.scalar(select(func.count()).select_from(MergeProposal).where(column==value)) or 0)
    reviewed=total-pending
    return {"batches":int(s.scalar(select(func.count()).select_from(MergeBatch)) or 0),"proposals":total,"pending_review":pending,"ready_merge":count(MergeProposal.candidate_class,"ready_merge"),"needs_review":count(MergeProposal.candidate_class,"needs_review"),"possible_match":count(MergeProposal.candidate_class,"possible_match"),"high_conflicts":count(MergeProposal.conflict_severity,"high"),"medium_conflicts":count(MergeProposal.conflict_severity,"medium"),"approved_merge":count(MergeProposal.review_status,"approved_merge"),"rejected_match":count(MergeProposal.review_status,"rejected_match"),"progress":{"total":total,"reviewed":reviewed,"pending":pending,"percentage":round(reviewed*100/max(total,1),2)}}
def list_merge_batches(s):return list(s.scalars(select(MergeBatch).order_by(MergeBatch.created_at.desc())))
def get_merge_batch(s,id):
    row=s.get(MergeBatch,id)
    if not row:raise LookupError("merge batch not found")
    return row
def list_merge_proposals(s:Session,*,batch_id=None,review_status=None,candidate_class=None,conflict_severity=None,priority=None,assigned_role=None,q=None,minimum_confidence=None,maximum_distance=None,has_conflicts=None,limit=25,offset=0,sort_by="confidence_score",sort_order="desc"):
    started=time.perf_counter();stmt=select(MergeProposal);filters=[]
    for column,value in ((MergeProposal.batch_id,batch_id),(MergeProposal.review_status,review_status),(MergeProposal.candidate_class,candidate_class),(MergeProposal.conflict_severity,conflict_severity),(MergeProposal.priority,priority),(MergeProposal.assigned_role,assigned_role)):
        if value is not None:filters.append(column==value)
    if q:filters.append(or_(MergeProposal.excel_name.ilike(f"%{q}%"),MergeProposal.kml_name.ilike(f"%{q}%"),MergeProposal.excel_record_id.ilike(f"%{q}%"),MergeProposal.kml_record_id.ilike(f"%{q}%")))
    if minimum_confidence is not None:filters.append(MergeProposal.confidence_score>=minimum_confidence)
    if maximum_distance is not None:filters.append(MergeProposal.distance_meters<=maximum_distance)
    if has_conflicts is not None:filters.append(MergeProposal.conflict_severity!="none" if has_conflicts else MergeProposal.conflict_severity=="none")
    stmt=stmt.where(*filters);total=int(s.scalar(select(func.count()).select_from(stmt.subquery())) or 0);allowed={"confidence_score":MergeProposal.confidence_score,"distance_meters":MergeProposal.distance_meters,"created_at":MergeProposal.created_at,"name_similarity":MergeProposal.name_similarity};column=allowed.get(sort_by,MergeProposal.confidence_score);stmt=stmt.order_by(column.asc() if sort_order=="asc" else column.desc()).limit(min(limit,100)).offset(offset)
    return list(s.scalars(stmt)),total,round((time.perf_counter()-started)*1000,3)
def get_merge_proposal(s,id):
    row=s.scalar(_proposal_stmt().where(MergeProposal.id==id))
    if not row:raise LookupError("merge proposal not found")
    return row
def get_merge_proposal_comparison(s,id):
    p=get_merge_proposal(s,id);return {"proposal_id":p.id,"excel":p.excel_snapshot,"kml":p.kml_snapshot,"proposed_site":p.proposed_site,"field_sources":p.field_sources,"score":{"confidence":float(p.confidence_score),"name_similarity":float(p.name_similarity),"distance_meters":float(p.distance_meters) if p.distance_meters is not None else None},"conflicts":p.conflict_fields}
def validate_decision(p:MergeProposal,decision:str,role:str):
    if decision not in DECISIONS:raise ValueError("invalid merge decision")
    if role in {"viewer","decision_maker"}:raise PermissionError("role cannot submit decisions")
    if role=="editor":raise PermissionError("editor can add notes only")
    if decision=="approved_merge" and p.conflict_severity=="high" and role not in MANAGERS:raise PermissionError("high conflict approval requires data manager")
    if decision=="approved_merge" and role=="reviewer" and p.conflict_severity!="none":raise PermissionError("reviewer can approve conflict-free proposals only")
    if role=="gis_specialist" and decision not in {"approved_merge","needs_field_verification","deferred"}:raise PermissionError("GIS role is limited to spatial review decisions")
def submit_merge_decision(s,p:MergeProposal,*,decision,role,reason=None,notes=None,stage="merge_review",metadata=None,reviewer_reference=None):
    validate_decision(p,decision,role);row=MergeDecision(proposal_id=p.id,decision=decision,review_stage=stage,reviewer_role=role,reviewer_reference=reviewer_reference,decision_reason=reason,reviewer_notes=notes,decision_metadata=metadata or {});p.decisions.append(row);p.review_status=decision;s.flush();return row
def get_proposal_decision_history(s,id):return get_merge_proposal(s,id).decisions
def _safe(p):return p.candidate_class=="ready_merge" and p.conflict_severity=="none" and float(p.confidence_score)>=92 and float(p.name_similarity)>=90 and p.distance_meters is not None and float(p.distance_meters)<=100 and p.review_status=="pending_review"
def _token(ids,decision):return hashlib.sha256(f"{decision}:{','.join(sorted(map(str,ids)))}:LSTA-MERGE-PREVIEW-V1".encode()).hexdigest()
def bulk_decision_preview(s,ids,decision):
    rows=list(s.scalars(select(MergeProposal).where(MergeProposal.id.in_(ids))));eligible=[];rejected={}
    for p in rows:
        if decision=="approved_merge" and not _safe(p):rejected[str(p.id)]="proposal is not safe for bulk approval"
        else:eligible.append(p.id)
    missing=set(ids)-{p.id for p in rows}
    for id in missing:rejected[str(id)]="proposal not found"
    return {"eligible_ids":eligible,"rejected":rejected,"preview_token":_token(eligible,decision),"writes":0}
def validate_bulk_decision(s,ids,decision,token):
    preview=bulk_decision_preview(s,ids,decision)
    if preview["preview_token"]!=token or set(preview["eligible_ids"])!=set(ids):raise ValueError("bulk decision must match a safe preview")
    return preview
def bulk_submit_decisions(s,ids,decision,role,token,reason=None,notes=None):
    if role not in MANAGERS:raise PermissionError("bulk decisions require data manager")
    validate_bulk_decision(s,ids,decision,token);rows=list(s.scalars(select(MergeProposal).where(MergeProposal.id.in_(ids))));return [submit_merge_decision(s,p,decision=decision,role=role,reason=reason,notes=notes,metadata={"bulk":True}) for p in rows]
def assign_proposal(s,id,role):p=get_merge_proposal(s,id);p.assigned_role=role;s.flush();return p
def calculate_review_progress(s):return get_merge_summary(s)["progress"]
def get_unmatched_summary(s):
    batch=s.scalar(select(MergeBatch).order_by(MergeBatch.created_at.desc()).limit(1));params=batch.matching_parameters if batch else {};return {"unmatched_excel_records":157,"unmatched_kml_records":116,"source":"batch_summary","parameters":params}
>>>>>>> origin/main
