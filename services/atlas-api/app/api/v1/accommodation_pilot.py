from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models import MergeDecision, MergeProposal
from app.models.tables import MergeExecutionBatch
from app.services.accommodation_pilot_selection_service import (
    list_pilot_candidates,
    score_pilot_safety,
    select_pilot_sample,
)
from app.services.accommodation_pilot_verification_service import generate_pilot_verification_report
from app.services.merge_rollback_service import preview_rollback
from app.services.pilot_release_gate_service import generate_release_gate_decision

router=APIRouter(prefix="/api/v1/accommodation-pilot",tags=["accommodation-pilot"])
def _roles(role):
    if role not in {"data_manager","system_admin","decision_maker","reviewer","gis_specialist"}:raise HTTPException(403,"pilot access forbidden")
@router.get("/candidates")
def candidates(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_roles(role);return [{"proposal_id":str(p.id),"name":p.excel_name,"safety_score":score_pilot_safety(p)}for p in list_pilot_candidates(db)[:25]]
@router.post("/select")
def select_sample(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_roles(role);return [{"proposal_id":str(p.id),"safety_score":score_pilot_safety(p)}for p in select_pilot_sample(db)]
@router.get("/execution-batch")
def batch(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_roles(role);b=db.scalar(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()));return None if not b else {"id":str(b.id),"status":b.status,"items":len(b.items),"dry_run":b.dry_run_report}
@router.get("/verification")
def verification(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_roles(role);b=db.scalar(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()));return [] if not b else generate_pilot_verification_report(db,b.items)
@router.get("/report")
def report(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):return {"scope":5,"publication":False,"promotion":False,"visit_libya":False,"verification":verification(role,db)}
@router.get("/readiness")
def readiness(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    _roles(role);b=db.scalar(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()));verified=bool(b and len(b.items)==5 and all(x.execution_status=="completed" for x in b.items));rollbacks=sum(bool(preview_rollback(x).get("restore_plan")) for x in b.items) if b else 0
    return generate_release_gate_decision(True,verified,rollbacks==5)

def _proposal(db,id):
    p=db.get(MergeProposal,id)
    if not p:raise HTTPException(404,"proposal not found")
    return p
def _detail(p,role):
    history=[{"stage":d.review_stage,"decision":d.decision,"reviewer_role":d.reviewer_role,"reviewer_reference":d.reviewer_reference if role in {"data_manager","system_admin"} else None,"timestamp":d.decided_at,"reason":d.decision_reason,"notes":d.reviewer_notes}for d in p.decisions]
    return {"proposal":{"id":str(p.id),"excel_record_id":p.excel_record_id,"kml_record_id":p.kml_record_id,"candidate_class":p.candidate_class,"confidence_score":float(p.confidence_score),"name_similarity":float(p.name_similarity),"distance_meters":float(p.distance_meters or 0),"conflict_severity":p.conflict_severity,"conflict_fields":p.conflict_fields,"review_status":p.review_status},"excel":p.excel_snapshot,"kml":p.kml_snapshot,"proposed":{**p.proposed_site,"field_sources":p.field_sources},"review":{"history":history,"completed_stages":[x["stage"]for x in history if x["decision"]in {"accepted","approved_merge"}],"blockers":[]}}
@router.get("/reviews/{proposal_id}")
def review_detail(proposal_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_roles(role);return _detail(_proposal(db,proposal_id),role)
@router.get("/reviews/{proposal_id}/history")
def review_history(proposal_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):return _detail(_proposal(db,proposal_id),role)["review"]["history"]
@router.get("/reviews/{proposal_id}/comparison")
def comparison(proposal_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):d=_detail(_proposal(db,proposal_id),role);return {k:d[k]for k in("excel","kml","proposed")}
@router.get("/reviews/{proposal_id}/map-data")
def map_data(proposal_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    p=_proposal(db,proposal_id);return {"excel":None,"kml":[p.kml_snapshot.get("longitude"),p.kml_snapshot.get("latitude")],"distance_meters":float(p.distance_meters or 0)}
def _decide(id,stage,payload,role,db):
    allowed={"technical":{"technical_reviewer","system_admin"},"gis":{"gis_specialist","system_admin"},"data":{"data_reviewer","system_admin"},"final":{"data_manager","system_admin"}}
    if role not in allowed[stage]:raise HTTPException(403,"role is not authorized for this stage")
    decision=payload.get("decision");notes=payload.get("notes")
    if decision in {"rejected","needs_correction"}and not notes:raise HTTPException(422,"notes are required")
    p=_proposal(db,id);order=["technical","gis","data","final"];latest={d.review_stage:d.decision for d in p.decisions}
    if any(latest.get(x)not in {"accepted","approved_merge"}for x in order[:order.index(stage)]):raise HTTPException(409,"previous review stage is incomplete")
    stored="approved_merge"if stage=="final"and decision=="accepted"else decision;p.decisions.append(MergeDecision(decision=stored,review_stage=stage,reviewer_role=role,reviewer_notes=notes,decision_reason=payload.get("reason"),decision_metadata={"pilot":True,"separation_of_duties_not_fully_enforced":True}));p.review_status="approved_merge"if stored=="approved_merge"else("blocked"if stored=="rejected"else p.review_status);db.commit();return _detail(p,role)
for _stage in("technical","gis","data","final"):
    router.add_api_route(f"/reviews/{{proposal_id}}/{_stage}",lambda proposal_id,payload,role=Depends(get_reviewer_role),db=Depends(get_db),stage=_stage:_decide(proposal_id,stage,payload,role,db),methods=["POST"])
@router.post("/rollback-preview/{item_id}")
def rollback(item_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    _roles(role);b=db.scalar(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()));item=next((x for x in b.items if str(x.id)==item_id),None) if b else None
    if not item:raise HTTPException(404,"item not found")
    return preview_rollback(item)
