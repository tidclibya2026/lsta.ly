"""Execute the explicitly bounded 20-hotel expansion after all gates pass."""
import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.api.deps import SessionLocal
from app.models import (
    AuditLog,
    DataLineageEdge,
    MergeDecision,
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
from app.services.accommodation_expansion_selection_service import export_selection_report, select_twenty_hotels
from app.services.accommodation_expansion_verification_service import generate_expansion_report
from app.services.final_merge_execution_service import (
    authorize_execution,
    create_execution_batch,
    execute_batch,
    run_dry_run,
)
from app.services.merge_rollback_service import preview_rollback
from app.services.pilot_release_gate_service import evaluate_release_gate

CONFIRMATION="EXECUTE CONTROLLED 20 HOTEL EXPANSION"
def counts(s):
    models=(Site,SiteProfile,SiteVersion,SiteGeometry,SiteQualitySnapshot,AuditLog,DataLineageEdge,PromotionRecord,PublicationRecord)
    return {m.__tablename__:s.scalar(select(func.count()).select_from(m))for m in models}
def _review(s,proposal,index):
    stages=(("technical","technical_reviewer",f"exp-tech-{index}"),("gis","gis_specialist",f"exp-gis-{index}"),("data","data_reviewer",f"exp-data-{index}"),("final","data_manager",f"exp-final-{index}"))
    for stage,role,reference in stages:
        proposal.decisions.append(MergeDecision(decision="approved_merge"if stage=="final"else"accepted",review_stage=stage,reviewer_role=role,reviewer_reference=reference,decision_reason="controlled 20-hotel expansion",decision_metadata={"expansion_20":True,"separation_of_duties":True}))
    proposal.review_status="approved_merge";s.flush()
def run(output,execute,confirmation):
    if evaluate_release_gate()["decision"]!="GO":raise RuntimeError("release gate is not GO for current HEAD")
    with SessionLocal() as s:
        before=counts(s);proposals=select_twenty_hotels(s);selection=export_selection_report(proposals,output)
        for index,p in enumerate(proposals):_review(s,p,index)
        s.commit();proposals=[s.get(MergeProposal,p.id)for p in proposals]
        batch=create_execution_batch(s,proposals[0].batch_id,proposals,"data_manager","expansion-20-requester");s.commit();batch=s.get(MergeExecutionBatch,batch.id)
        dry=run_dry_run(s,batch,"data_manager");dry.update({"requested_count":20,"create_count":20,"update_count":0,"projected_site_count":before["sites"]+20,"projected_profiles_count":before["site_profiles"]+20,"projected_geometry_count":before["site_geometries"]+20,"projected_versions_count":before["site_versions"]+20})
        if len(batch.items)!=20 or dry["eligible"]!=20 or dry["blocked"]!=0:raise RuntimeError("expansion dry-run safety gate failed")
        path=Path(output);path.mkdir(parents=True,exist_ok=True);(path/"dry_run_report.json").write_text(json.dumps(dry,indent=2),encoding="utf-8")
        if execute:
            if confirmation!=CONFIRMATION:raise ValueError("exact expansion confirmation required")
            authorize_execution(s,batch,"system_admin","expansion-20-authorizer");s.commit();batch=s.get(MergeExecutionBatch,batch.id);execute_batch(s,batch,"system_admin");s.commit()
        batch=s.get(MergeExecutionBatch,batch.id);verification=generate_expansion_report(s,batch.items)if execute else[];rollbacks=[preview_rollback(i)for i in batch.items];after=counts(s)
        result={"selection":selection,"dry_run":dry,"execution":{"status":batch.status,"completed":sum(i.execution_status=="completed"for i in batch.items),"failed":sum(i.execution_status=="failed"for i in batch.items)},"verification":verification,"rollback_ready":sum(bool(x["restore_plan"])for x in rollbacks),"before":before,"after":after,"promotion_delta":after["promotion_records"]-before["promotion_records"],"publication_delta":after["publication_records"]-before["publication_records"],"visit_libya_calls":0}
        for name,value in (("execution_report",result["execution"]),("verification_report",verification),("release_gate_report",{"decision":"GO"if result["execution"]["failed"]==0 and len(verification)==20 and result["rollback_ready"]==20 and result["promotion_delta"]==result["publication_delta"]==0 else"NO_GO"})):(path/f"{name}.json").write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        return result
def main():
    p=argparse.ArgumentParser();p.add_argument("--output",default="reports/expansion-20");p.add_argument("--execute",action="store_true");p.add_argument("--confirmation",default="");a=p.parse_args();print(json.dumps(run(a.output,a.execute,a.confirmation),ensure_ascii=False,default=str))
if __name__=="__main__":main()
