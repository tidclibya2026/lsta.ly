from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models import MergeExecutionBatch, MergeExecutionEvent, MergeExecutionItem, MergeProposal
from app.schemas.merge_execution import (
    AuthorizationRequest,
    BatchRequest,
    ExecuteRequest,
    PreviewRequest,
    RollbackRequest,
)
from app.services.final_merge_execution_service import (
    authorize_execution,
    create_execution_batch,
    execute_batch,
    run_dry_run,
)
from app.services.merge_execution_preview_service import create_execution_preview, get_execution_preview
from app.services.merge_rollback_service import execute_rollback, preview_rollback

router=APIRouter(prefix="/api/v1/merge-execution",tags=["merge-execution"])
def _visible(role):
    if role=="viewer": raise HTTPException(403,"وحدة التنفيذ غير متاحة للمشاهد")
def _batch(db,id):
    row=db.get(MergeExecutionBatch,id)
    if not row: raise HTTPException(404,"دفعة التنفيذ غير موجودة")
    return row
def _item(db,id):
    row=db.get(MergeExecutionItem,id)
    if not row: raise HTTPException(404,"عنصر التنفيذ غير موجود")
    return row
def _serialize(b): return {"id":str(b.id),"execution_code":b.execution_code,"status":b.status,"execution_mode":b.execution_mode,"requested_proposal_count":b.requested_proposal_count,"eligible_proposal_count":b.eligible_proposal_count,"executed_proposal_count":b.executed_proposal_count,"failed_proposal_count":b.failed_proposal_count,"dry_run_report":b.dry_run_report,"validation_summary":b.validation_summary}

@router.post("/preview")
def preview(p:PreviewRequest,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    _visible(role);proposal=db.get(MergeProposal,p.proposal_id)
    if not proposal: raise HTTPException(404,"المقترح غير موجود")
    return create_execution_preview(db,proposal,p.operation_type,p.target_site_id)
@router.get("/previews/{execution_id}")
def stored_preview(execution_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return get_execution_preview(_item(db,execution_id))
@router.post("/batches")
def create(p:BatchRequest,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    proposals=list(db.scalars(select(MergeProposal).where(MergeProposal.id.in_(p.proposal_ids))))
    try:b=create_execution_batch(db,p.merge_batch_id,proposals,role,p.requester_reference,p.operation_type);db.commit();db.refresh(b);return _serialize(b)
    except (PermissionError,ValueError) as e:db.rollback();raise HTTPException(403,str(e)) from e
@router.get("/batches")
def batches(role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return [_serialize(x) for x in db.scalars(select(MergeExecutionBatch).order_by(MergeExecutionBatch.created_at.desc()).limit(100))]
@router.get("/batches/{batch_id}")
def batch(batch_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return _serialize(_batch(db,batch_id))
@router.post("/batches/{batch_id}/dry-run")
def dry_run(batch_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    try:r=run_dry_run(db,_batch(db,batch_id),role);db.commit();return r
    except (PermissionError,ValueError) as e:db.rollback();raise HTTPException(403,str(e)) from e
@router.post("/batches/{batch_id}/authorize")
def authorize(batch_id:UUID,p:AuthorizationRequest,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    if p.confirmation!="AUTHORIZE APPROVED MERGES":raise HTTPException(400,"نص التأكيد غير صحيح")
    try:b=_batch(db,batch_id);authorize_execution(db,b,role,p.authorizer_reference);db.commit();return _serialize(b)
    except (PermissionError,ValueError) as e:db.rollback();raise HTTPException(403,str(e)) from e
@router.post("/batches/{batch_id}/execute")
def execute(batch_id:UUID,p:ExecuteRequest,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    if p.confirmation!="EXECUTE APPROVED MERGES":raise HTTPException(400,"نص التأكيد غير صحيح")
    try:b=_batch(db,batch_id);execute_batch(db,b,role);db.commit();return _serialize(b)
    except (PermissionError,ValueError) as e:db.rollback();raise HTTPException(403,str(e)) from e
@router.post("/batches/{batch_id}/cancel")
def cancel(batch_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    if role not in {"data_manager","system_admin"}:raise HTTPException(403,"غير مخول")
    b=_batch(db,batch_id);b.status="cancelled";db.commit();return _serialize(b)
@router.get("/items/{item_id}")
def item(item_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return get_execution_preview(_item(db,item_id))
@router.get("/items/{item_id}/events")
def events(item_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return [{"event_type":e.event_type,"event_payload":e.event_payload,"occurred_at":e.occurred_at} for e in db.scalars(select(MergeExecutionEvent).where(MergeExecutionEvent.execution_item_id==item_id).order_by(MergeExecutionEvent.occurred_at))]
@router.post("/items/{item_id}/rollback-preview")
def rollback_preview(item_id:UUID,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):_visible(role);return preview_rollback(_item(db,item_id))
@router.post("/items/{item_id}/rollback")
def rollback(item_id:UUID,p:RollbackRequest,role=Depends(get_reviewer_role),db:Session=Depends(get_db)):
    if role!="system_admin" or p.confirmation!="ROLLBACK CONTROLLED MERGE":raise HTTPException(403,"الاسترجاع الفعلي مقيد")
    execute_rollback(db,_item(db,item_id),allow=True);db.commit();return {"status":"rolled_back"}
