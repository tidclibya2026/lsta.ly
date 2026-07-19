<<<<<<< HEAD
﻿from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
=======
from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
>>>>>>> origin/main
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
<<<<<<< HEAD
from app.schemas.merge_review import (
    BulkDecisionPreviewRequest,
    BulkDecisionRequest,
    MergeDecisionRequest,
)
from app.services.merge_review_query_service import (
=======
from app.schemas.merge_review import BulkDecisionPreviewRequest, BulkDecisionRequest, MergeDecisionRequest
from app.services.merge_review_service import (
>>>>>>> origin/main
    assign_proposal,
    bulk_decision_preview,
    bulk_submit_decisions,
    get_merge_batch,
<<<<<<< HEAD
=======
    get_merge_proposal,
>>>>>>> origin/main
    get_merge_proposal_comparison,
    get_merge_summary,
    get_proposal_decision_history,
    get_unmatched_summary,
    list_merge_batches,
    list_merge_proposals,
    submit_merge_decision,
)
<<<<<<< HEAD
from app.services.merge_review_service import get_merge_proposal

router = APIRouter(
    prefix="/api/v1/merge-review",
    tags=["merge-review"],
)

ReviewerRole = Annotated[str, Depends(get_reviewer_role)]


READ_ROLES = {
    "decision_maker",
    "editor",
    "reviewer",
    "gis_specialist",
    "data_manager",
    "system_admin",
}

MANAGE_ROLES = {
    "data_manager",
    "system_admin",
}


class AssignmentRequest(BaseModel):
    assigned_role: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Reviewer role assigned to the merge proposal.",
    )


def require_role(
    role: str,
    allowed_roles: set[str],
) -> None:
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this operation.",
        )


def rollback_quietly(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def get_required_resource(
    service_function: Any,
    db: Session,
    identifier: UUID,
) -> Any:
    resource = service_function(db, identifier)

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested merge-review resource was not found.",
        )

    return resource


def serialize_batch(batch: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(batch.id),
    }

    optional_fields = (
        "batch_code",
        "entity_type",
        "proposal_count",
        "status",
        "source_reference",
        "notes",
        "created_at",
        "updated_at",
        "completed_at",
    )

    for field_name in optional_fields:
        if hasattr(batch, field_name):
            data[field_name] = getattr(batch, field_name)

    return data


def serialize_proposal(proposal: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(proposal.id),
    }

    uuid_fields = (
        "batch_id",
        "excel_record_id",
        "kml_record_id",
    )

    for field_name in uuid_fields:
        if hasattr(proposal, field_name):
            value = getattr(proposal, field_name)
            data[field_name] = str(value) if value is not None else None

    normal_fields = (
        "excel_name",
        "kml_name",
        "candidate_class",
        "conflict_severity",
        "review_status",
        "priority",
        "assigned_role",
        "conflict_fields",
        "excel_snapshot",
        "kml_snapshot",
        "proposed_site",
        "field_sources",
        "created_at",
        "updated_at",
    )

    for field_name in normal_fields:
        if hasattr(proposal, field_name):
            data[field_name] = getattr(proposal, field_name)

    numeric_fields = (
        "confidence_score",
        "name_similarity",
        "distance_meters",
    )

    for field_name in numeric_fields:
        if hasattr(proposal, field_name):
            value = getattr(proposal, field_name)
            data[field_name] = float(value) if value is not None else None

    return data


def serialize_decision(
    decision: Any,
    *,
    privileged: bool,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(decision.id),
    }

    optional_fields = (
        "decision",
        "review_stage",
        "reviewer_role",
        "decision_reason",
        "reviewer_notes",
        "decision_metadata",
        "decided_at",
        "created_at",
    )

    for field_name in optional_fields:
        if hasattr(decision, field_name):
            data[field_name] = getattr(decision, field_name)

    if privileged and hasattr(decision, "reviewer_reference"):
        data["reviewer_reference"] = decision.reviewer_reference

    if hasattr(decision, "proposal_id"):
        proposal_id = decision.proposal_id
        data["proposal_id"] = (
            str(proposal_id)
            if proposal_id is not None
            else None
        )

    return data


@router.get("/summary")
def read_merge_summary(
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> Any:
    require_role(role, READ_ROLES)
    return get_merge_summary(db)


@router.get("/batches")
def read_merge_batches(
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    batches = list_merge_batches(db)

    return {
        "items": [
            serialize_batch(batch)
            for batch in batches
        ],
        "total_count": len(batches),
    }


@router.get("/batches/{batch_id}")
def read_merge_batch(
    batch_id: UUID,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    batch = get_required_resource(
        get_merge_batch,
        db,
        batch_id,
    )

    return serialize_batch(batch)


@router.get("/batches/{batch_id}/proposals")
def read_batch_proposals(
    batch_id: UUID,
    role: ReviewerRole,
    review_status: str | None = None,
    candidate_class: str | None = None,
    conflict_severity: str | None = None,
    priority: str | None = None,
    assigned_role: str | None = None,
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=250,
    ),
    minimum_confidence: float | None = Query(
        default=None,
        ge=0,
        le=100,
    ),
    maximum_distance: float | None = Query(
        default=None,
        ge=0,
    ),
    has_conflicts: bool | None = None,
    limit: int = Query(
        default=25,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    sort_by: str = Query(
        default="confidence_score",
        min_length=1,
        max_length=100,
    ),
    sort_order: str = Query(
        default="desc",
        pattern="^(asc|desc)$",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    get_required_resource(
        get_merge_batch,
        db,
        batch_id,
    )

    result = list_merge_proposals(
        db,
        batch_id=batch_id,
        review_status=review_status,
        candidate_class=candidate_class,
        conflict_severity=conflict_severity,
        priority=priority,
        assigned_role=assigned_role,
        q=q,
        minimum_confidence=minimum_confidence,
        maximum_distance=maximum_distance,
        has_conflicts=has_conflicts,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    if isinstance(result, tuple):
        if len(result) == 3:
            rows, total_count, query_execution_ms = result
        elif len(result) == 2:
            rows, total_count = result
            query_execution_ms = None
        else:
            rows = result[0]
            total_count = len(rows)
            query_execution_ms = None
    else:
        rows = result
        total_count = len(rows)
        query_execution_ms = None

    applied_filters = {
        key: value
        for key, value in {
            "review_status": review_status,
            "candidate_class": candidate_class,
            "conflict_severity": conflict_severity,
            "priority": priority,
            "assigned_role": assigned_role,
            "q": q,
            "minimum_confidence": minimum_confidence,
            "maximum_distance": maximum_distance,
            "has_conflicts": has_conflicts,
        }.items()
        if value is not None
    }

    return {
        "items": [
            serialize_proposal(row)
            for row in rows
        ],
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total_count,
        "query_execution_ms": query_execution_ms,
        "applied_filters": applied_filters,
    }


@router.get("/proposals/{proposal_id}")
def read_merge_proposal(
    proposal_id: UUID,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    proposal = get_required_resource(
        get_merge_proposal,
        db,
        proposal_id,
    )

    data = serialize_proposal(proposal)

    decisions = getattr(proposal, "decisions", None) or []

    data["history"] = [
        serialize_decision(
            decision,
            privileged=role in MANAGE_ROLES,
        )
        for decision in decisions
    ]

    return data


@router.get("/proposals/{proposal_id}/comparison")
def read_merge_proposal_comparison(
    proposal_id: UUID,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> Any:
    require_role(role, READ_ROLES)

    comparison = get_merge_proposal_comparison(
        db,
        proposal_id,
    )

    if comparison is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested merge proposal was not found.",
        )

    return comparison


@router.get("/proposals/{proposal_id}/history")
def read_merge_proposal_history(
    proposal_id: UUID,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    get_required_resource(
        get_merge_proposal,
        db,
        proposal_id,
    )

    decisions = get_proposal_decision_history(
        db,
        proposal_id,
    )

    return {
        "items": [
            serialize_decision(
                decision,
                privileged=role in MANAGE_ROLES,
            )
            for decision in decisions
        ],
        "total_count": len(decisions),
    }


@router.post(
    "/proposals/{proposal_id}/decision",
    status_code=status.HTTP_201_CREATED,
)
def create_merge_proposal_decision(
    proposal_id: UUID,
    payload: MergeDecisionRequest,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, READ_ROLES)

    proposal = get_required_resource(
        get_merge_proposal,
        db,
        proposal_id,
    )

    try:
        decision_row = submit_merge_decision(
            db,
            proposal,
            decision=payload.decision,
            role=role,
            reason=payload.decision_reason,
            notes=payload.reviewer_notes,
            stage=payload.review_stage,
            metadata=payload.decision_metadata,
        )

        db.commit()
        db.refresh(proposal)
        db.refresh(decision_row)

    except ValueError as exc:
        rollback_quietly(db)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except HTTPException:
        rollback_quietly(db)
        raise

    except Exception:
        rollback_quietly(db)
        raise

    return {
        "proposal_id": str(proposal.id),
        "decision_id": str(decision_row.id),
        "review_status": getattr(
            proposal,
            "review_status",
            None,
        ),
        "automatic_merge": False,
        "promotion_created": False,
    }


@router.post("/proposals/{proposal_id}/assign")
def assign_merge_proposal(
    proposal_id: UUID,
    payload: AssignmentRequest,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, MANAGE_ROLES)

    try:
        proposal = assign_proposal(
            db,
            proposal_id,
            payload.assigned_role,
        )

        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested merge proposal was not found.",
            )

        db.commit()
        db.refresh(proposal)

    except ValueError as exc:
        rollback_quietly(db)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except HTTPException:
        rollback_quietly(db)
        raise

    except Exception:
        rollback_quietly(db)
        raise

    return serialize_proposal(proposal)


@router.post("/bulk-preview")
def preview_bulk_merge_decision(
    payload: BulkDecisionPreviewRequest,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, MANAGE_ROLES)

    try:
        result = bulk_decision_preview(
            db,
            payload.proposal_ids,
            payload.decision,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if not isinstance(result, dict):
        return {
            "result": result,
        }

    eligible_ids = result.get("eligible_ids")

    if eligible_ids is not None:
        result["eligible_ids"] = [
            str(proposal_id)
            for proposal_id in eligible_ids
        ]

    return result


@router.post(
    "/bulk-decision",
    status_code=status.HTTP_201_CREATED,
)
def create_bulk_merge_decision(
    payload: BulkDecisionRequest,
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_role(role, MANAGE_ROLES)

    try:
        decision_rows = bulk_submit_decisions(
            db,
            payload.proposal_ids,
            payload.decision,
            role,
            payload.preview_token,
            payload.decision_reason,
            payload.reviewer_notes,
        )

        db.commit()

    except ValueError as exc:
        rollback_quietly(db)

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except HTTPException:
        rollback_quietly(db)
        raise

    except Exception:
        rollback_quietly(db)
        raise

    return {
        "decisions_created": len(decision_rows),
        "proposal_ids": [
            str(decision.proposal_id)
            for decision in decision_rows
            if hasattr(decision, "proposal_id")
        ],
        "automatic_merge": False,
    }


@router.get("/unmatched-summary")
def read_unmatched_summary(
    role: ReviewerRole,
    db: Session = Depends(get_db),
) -> Any:
    require_role(role, READ_ROLES)
    return get_unmatched_summary(db)
=======

router=APIRouter(prefix="/api/v1/merge-review",tags=["merge-review"]);Role=Annotated[str,Depends(get_reviewer_role)];READ={"decision_maker","editor","reviewer","gis_specialist","data_manager","system_admin"};MANAGE={"data_manager","system_admin"}
class Assignment(BaseModel):assigned_role:str
def require(role,allowed):
    if role not in allowed:raise HTTPException(403,"لا توجد صلاحية لمساحة مراجعة الدمج")
def batch_dict(x,detail=False):
    data={"id":str(x.id),"batch_code":x.batch_code,"entity_type":x.entity_type,"proposal_count":x.proposal_count,"status":x.status}
    if detail:data.update({"excel_file_name":x.excel_file_name,"kml_file_name":x.kml_file_name,"excel_record_count":x.excel_record_count,"kml_record_count":x.kml_record_count,"raw_candidate_count":x.raw_candidate_count,"engine_version":x.engine_version,"matching_parameters":x.matching_parameters})
    return data
def item_dict(x):return {"id":str(x.id),"batch_id":str(x.batch_id),"excel_record_id":x.excel_record_id,"kml_record_id":x.kml_record_id,"excel_name":x.excel_name,"kml_name":x.kml_name,"confidence_score":float(x.confidence_score),"name_similarity":float(x.name_similarity),"distance_meters":float(x.distance_meters) if x.distance_meters is not None else None,"candidate_class":x.candidate_class,"conflict_severity":x.conflict_severity,"review_status":x.review_status,"priority":x.priority,"assigned_role":x.assigned_role}
def history_dict(x,privileged=False):
    data={"id":str(x.id),"decision":x.decision,"review_stage":x.review_stage,"reviewer_role":x.reviewer_role,"decision_reason":x.decision_reason,"reviewer_notes":x.reviewer_notes,"decided_at":x.decided_at}
    if privileged:data["reviewer_reference"]=x.reviewer_reference
    return data
def lookup(call,*args):
    try:return call(*args)
    except LookupError as e:raise HTTPException(404,str(e)) from e
@router.get("/summary")
def summary(role:Role,db:Session=Depends(get_db)):return get_merge_summary(db)
@router.get("/batches")
def batches(role:Role,db:Session=Depends(get_db)):require(role,READ);return {"items":[batch_dict(x) for x in list_merge_batches(db)]}
@router.get("/batches/{id}")
def batch(id:UUID,role:Role,db:Session=Depends(get_db)):require(role,READ);return batch_dict(lookup(get_merge_batch,db,id),True)
@router.get("/batches/{id}/proposals")
def batch_proposals(id:UUID,role:Role,review_status:str|None=None,candidate_class:str|None=None,conflict_severity:str|None=None,priority:str|None=None,assigned_role:str|None=None,q:str|None=None,minimum_confidence:float|None=Query(None,ge=0,le=100),maximum_distance:float|None=Query(None,ge=0),has_conflicts:bool|None=None,limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0),sort_by:str="confidence_score",sort_order:str="desc",db:Session=Depends(get_db)):
    require(role,READ);lookup(get_merge_batch,db,id);rows,total,ms=list_merge_proposals(db,batch_id=id,review_status=review_status,candidate_class=candidate_class,conflict_severity=conflict_severity,priority=priority,assigned_role=assigned_role,q=q,minimum_confidence=minimum_confidence,maximum_distance=maximum_distance,has_conflicts=has_conflicts,limit=limit,offset=offset,sort_by=sort_by,sort_order=sort_order);result={"items":[item_dict(x) for x in rows],"total_count":total,"limit":limit,"offset":offset,"has_more":offset+limit<total,"applied_filters":{k:v for k,v in locals().copy().items() if k in {"review_status","candidate_class","conflict_severity","priority","assigned_role","q","minimum_confidence","maximum_distance","has_conflicts"} and v is not None}}
    if os.getenv("LSTA_ENV")=="development":result["query_time_ms"]=ms
    return result
@router.get("/proposals/{id}")
def proposal(id:UUID,role:Role,db:Session=Depends(get_db)):
    require(role,READ);p=lookup(get_merge_proposal,db,id);return {**item_dict(p),"conflict_fields":p.conflict_fields,"excel_snapshot":p.excel_snapshot,"kml_snapshot":p.kml_snapshot,"proposed_site":p.proposed_site,"field_sources":p.field_sources,"history":[history_dict(x,role in MANAGE) for x in p.decisions]}
@router.get("/proposals/{id}/comparison")
def comparison(id:UUID,role:Role,db:Session=Depends(get_db)):require(role,READ);return lookup(get_merge_proposal_comparison,db,id)
@router.get("/proposals/{id}/history")
def history(id:UUID,role:Role,db:Session=Depends(get_db)):require(role,READ);return {"items":[history_dict(x,role in MANAGE) for x in lookup(get_proposal_decision_history,db,id)]}
@router.post("/proposals/{id}/decision")
def decision(id:UUID,payload:MergeDecisionRequest,role:Role,db:Session=Depends(get_db)):
    require(role,READ);p=lookup(get_merge_proposal,db,id)
    try:row=submit_merge_decision(db,p,decision=payload.decision,role=role,reason=payload.decision_reason,notes=payload.reviewer_notes,stage=payload.review_stage,metadata=payload.decision_metadata)
    except (PermissionError,ValueError) as e:raise HTTPException(403 if isinstance(e,PermissionError) else 422,str(e)) from e
    db.commit();return {"proposal_id":str(p.id),"decision_id":str(row.id),"review_status":p.review_status,"automatic_merge":False,"promotion_created":False}
@router.post("/proposals/{id}/assign")
def assign(id:UUID,payload:Assignment,role:Role,db:Session=Depends(get_db)):require(role,MANAGE);p=lookup(assign_proposal,db,id,payload.assigned_role);db.commit();return item_dict(p)
@router.post("/bulk-preview")
def bulk_preview(payload:BulkDecisionPreviewRequest,role:Role,db:Session=Depends(get_db)):require(role,MANAGE);result=bulk_decision_preview(db,payload.proposal_ids,payload.decision);return {**result,"eligible_ids":[str(x) for x in result["eligible_ids"]]}
@router.post("/bulk-decision")
def bulk_decision(payload:BulkDecisionRequest,role:Role,db:Session=Depends(get_db)):
    require(role,MANAGE)
    try:rows=bulk_submit_decisions(db,payload.proposal_ids,payload.decision,role,payload.preview_token,payload.decision_reason,payload.reviewer_notes)
    except (PermissionError,ValueError) as e:raise HTTPException(403 if isinstance(e,PermissionError) else 422,str(e)) from e
    db.commit();return {"decisions_created":len(rows),"proposal_ids":[str(x.proposal_id) for x in rows],"automatic_merge":False}
@router.get("/unmatched-summary")
def unmatched(role:Role,db:Session=Depends(get_db)):require(role,READ);return get_unmatched_summary(db)
>>>>>>> origin/main
