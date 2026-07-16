from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.schemas.merge_review import BulkDecisionPreviewRequest, BulkDecisionRequest, MergeDecisionRequest
from app.services.merge_review_service import (
    assign_proposal,
    bulk_decision_preview,
    bulk_submit_decisions,
    get_merge_batch,
    get_merge_proposal,
    get_merge_proposal_comparison,
    get_merge_summary,
    get_proposal_decision_history,
    get_unmatched_summary,
    list_merge_batches,
    list_merge_proposals,
    submit_merge_decision,
)

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
