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