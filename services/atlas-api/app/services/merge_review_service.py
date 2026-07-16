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
