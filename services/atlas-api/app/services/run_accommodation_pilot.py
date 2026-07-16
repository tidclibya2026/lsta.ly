"""Run the explicitly bounded five-hotel pilot. Requires --execute and exact confirmation."""
import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.api.deps import SessionLocal
from app.models import (
    AuditLog,
    DataLineageEdge,
    MergeProposal,
    PromotionRecord,
    PublicationRecord,
    Site,
    SiteGeometry,
    SiteProfile,
    SiteQualitySnapshot,
    SiteVersion,
)
from app.models.tables import MergeExecutionBatch
from app.services.accommodation_pilot_approval_service import submit_pilot_stage_decision
from app.services.accommodation_pilot_selection_service import export_pilot_selection_report, select_pilot_sample
from app.services.accommodation_pilot_verification_service import generate_pilot_verification_report
from app.services.final_merge_execution_service import (
    authorize_execution,
    create_execution_batch,
    execute_batch,
    run_dry_run,
)
from app.services.merge_rollback_service import preview_rollback


def counts(s):
    models=(Site,SiteProfile,SiteVersion,SiteGeometry,AuditLog,DataLineageEdge,SiteQualitySnapshot,PromotionRecord,PublicationRecord)
    return {m.__tablename__:s.scalar(select(func.count()).select_from(m)) for m in models}
def run(output,execute,confirmation):
    with SessionLocal() as s:
        before=counts(s);rows=select_pilot_sample(s);selection=export_pilot_selection_report(rows,output)
        for p in rows:
            for stage,ref in (("technical","pilot-tech-01"),("gis","pilot-gis-01"),("data","pilot-data-01"),("final","pilot-final-01")):submit_pilot_stage_decision(s,p,stage,ref)
        s.commit();rows=[s.get(MergeProposal,p.id) for p in rows]
        batch=create_execution_batch(s,rows[0].batch_id,rows,"data_manager","pilot-batch-requester","create_national_site");s.commit();batch=s.get(MergeExecutionBatch,batch.id)
        dry=run_dry_run(s,batch,"data_manager");s.commit()
        if len(batch.items)!=5 or dry["blocked"]!=0:raise RuntimeError("pilot safety gate blocked execution")
        if execute:
            if confirmation!="EXECUTE PILOT 5 APPROVED HOTELS":raise ValueError("exact pilot confirmation required")
            authorize_execution(s,batch,"system_admin","pilot-final-execution-authorizer");s.commit();batch=s.get(MergeExecutionBatch,batch.id);execute_batch(s,batch,"system_admin");s.commit()
        batch=s.get(MergeExecutionBatch,batch.id);verification=generate_pilot_verification_report(s,batch.items) if execute else []
        rollback=[preview_rollback(i) for i in batch.items];after=counts(s);report={"selection":selection,"dry_run":dry,"executed":execute,"execution_batch_id":str(batch.id),"status":batch.status,"verification":verification,"rollback_previews":rollback,"before":before,"after":after,"promotion_delta":after["promotion_records"]-before["promotion_records"],"publication_delta":after["publication_records"]-before["publication_records"],"visit_libya_calls":0}
        path=Path(output);path.mkdir(parents=True,exist_ok=True);(path/"accommodation_pilot_verification.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding="utf-8");(path/"accommodation_pilot_verification.md").write_text(f"# LSTA Accommodation Pilot\n\n- Status: {batch.status}\n- Selected: 5\n- Eligible: {dry['eligible']}\n- Blocked: {dry['blocked']}\n- Promotion delta: {report['promotion_delta']}\n- Publication delta: {report['publication_delta']}\n- Visit Libya calls: 0\n",encoding="utf-8");return report
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default="reports/pilot");p.add_argument("--execute",action="store_true");p.add_argument("--confirmation",default="");a=p.parse_args();print(json.dumps(run(a.output,a.execute,a.confirmation),ensure_ascii=False,default=str))
if __name__=="__main__":main()
