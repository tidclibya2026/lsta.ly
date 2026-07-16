from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models.tables import MergeExecutionBatch
from app.services.accommodation_pilot_selection_service import (
    list_pilot_candidates,
    score_pilot_safety,
    select_pilot_sample,
)
from app.services.accommodation_pilot_verification_service import generate_pilot_verification_report
from app.services.merge_rollback_service import preview_rollback

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
@router.post("/rollback-preview/{item_id}")
def rollback(item_id:str,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    _roles(role);b=db.scalar(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()));item=next((x for x in b.items if str(x.id)==item_id),None) if b else None
    if not item:raise HTTPException(404,"item not found")
    return preview_rollback(item)
