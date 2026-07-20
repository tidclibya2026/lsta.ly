from uuid import uuid4

from sqlalchemy import func, select

from app.models import MergeBatch, MergeProposal, PromotionRecord, PublicationRecord, Site
from app.models.tables import MergeExecutionBatch
from app.services.accommodation_pilot_approval_service import submit_pilot_stage_decision
from app.services.final_merge_execution_service import (
    authorize_execution,
    create_execution_batch,
    execute_batch,
    run_dry_run,
)
from app.services.merge_rollback_service import preview_rollback


def test_five_proposal_pilot_e2e(db_session):
    before_sites=db_session.scalar(select(func.count()).select_from(Site));before_promotions=db_session.scalar(select(func.count()).select_from(PromotionRecord));before_publications=db_session.scalar(select(func.count()).select_from(PublicationRecord))
    batch=MergeBatch(batch_code=f"TEST-{uuid4()}",entity_type="hotels",excel_file_name="synthetic.xlsx",excel_sha256="a"*64,kml_file_name="synthetic.kml",kml_sha256="b"*64,excel_record_count=5,kml_record_count=5,raw_candidate_count=5,proposal_count=5,engine_version="test",matching_parameters={},status="completed");db_session.add(batch);db_session.flush();proposals=[]
    for index in range(5):
        p=MergeProposal(batch_id=batch.id,excel_record_id=f"excel-{uuid4()}",kml_record_id=f"kml-{uuid4()}",excel_name=f"فندق اختبار {index}",kml_name=f"فندق اختبار {index}",confidence_score=100,name_similarity=100,distance_meters=0,candidate_class="ready_merge",conflict_severity="none",conflict_fields=[],excel_snapshot={"name_ar":f"فندق اختبار {index}"},kml_snapshot={"name_ar":f"فندق اختبار {index}","geometry_type":"Point","latitude":32+index/100,"longitude":13+index/100,"images":[]},proposed_site={"name_ar":f"فندق اختبار {index}"},field_sources={"name_ar":"excel","geometry":"kml"},review_status="pending_review",priority="normal");db_session.add(p);db_session.flush()
        for stage,ref in (("technical",f"tech-{index}"),("gis",f"gis-{index}"),("data",f"data-{index}"),("final",f"final-{index}")):submit_pilot_stage_decision(db_session,p,stage,ref)
        assert p.review_status=="approved_merge";proposals.append(p)
    execution=create_execution_batch(db_session,batch.id,proposals,"data_manager","e2e-requester");db_session.flush();db_session.expire_all();execution=db_session.get(MergeExecutionBatch,execution.id);dry=run_dry_run(db_session,execution,"data_manager");assert dry["eligible"]==5 and dry["blocked"]==0;authorize_execution(db_session,execution,"system_admin","e2e-authorizer");execute_batch(db_session,execution,"system_admin");db_session.flush()
    assert sum(i.execution_status=="completed" for i in execution.items)==5;assert sum(preview_rollback(i)["validation"]["valid"] for i in execution.items)==5
    assert db_session.scalar(select(func.count()).select_from(Site))==before_sites+5;assert db_session.scalar(select(func.count()).select_from(PromotionRecord))==before_promotions;assert db_session.scalar(select(func.count()).select_from(PublicationRecord))==before_publications
