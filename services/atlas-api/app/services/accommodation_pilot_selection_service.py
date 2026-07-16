"""Deterministic selection for the five-hotel activation pilot."""
import json
from pathlib import Path

from sqlalchemy import select

from app.models import MergeProposal
from app.models.tables import MergeExecutionItem

MAX_PILOT_ITEMS=5
def score_pilot_safety(p):
    distance=max(0,100-float(p.distance_meters or 0)*2)
    completeness=100 if p.excel_name and p.kml_name else 0
    return round(float(p.confidence_score)*.25+float(p.name_similarity)*.20+distance*.20+(100 if p.conflict_severity=="none" else 0)*.15+completeness*.10+100*.05+100*.05,2)
def list_pilot_candidates(session):
    q=select(MergeProposal).where(MergeProposal.candidate_class=="ready_merge",MergeProposal.conflict_severity=="none",MergeProposal.confidence_score>=95,MergeProposal.name_similarity>=95,MergeProposal.distance_meters<=50,MergeProposal.review_status.in_(("pending_review","approved_merge"))).order_by(MergeProposal.confidence_score.desc(),MergeProposal.name_similarity.desc(),MergeProposal.distance_meters,MergeProposal.id)
    return [p for p in session.scalars(q) if p.excel_name and p.kml_name and p.kml_snapshot.get("geometry_type")=="Point" and -180<=float(p.kml_snapshot.get("longitude",999))<=180 and -90<=float(p.kml_snapshot.get("latitude",999))<=90 and not session.scalar(select(MergeExecutionItem.id).where(MergeExecutionItem.proposal_id==p.id,MergeExecutionItem.execution_status.in_(("executing","completed"))))]
def select_pilot_sample(session,limit=5):
    if limit!=MAX_PILOT_ITEMS: raise ValueError("pilot must contain exactly five proposals")
    rows=[p for p in list_pilot_candidates(session) if score_pilot_safety(p)>=90][:limit]
    validate_pilot_sample(rows);return rows
def validate_pilot_sample(rows):
    if len(rows)!=MAX_PILOT_ITEMS: raise ValueError("exactly five safe proposals required")
    if len({p.id for p in rows})!=5: raise ValueError("duplicate proposal")
    return True
def export_pilot_selection_report(rows,output):
    data=[{"proposal_id":str(p.id),"excel_record_id":p.excel_record_id,"kml_record_id":p.kml_record_id,"excel_name":p.excel_name,"kml_name":p.kml_name,"confidence_score":float(p.confidence_score),"name_similarity":float(p.name_similarity),"distance_meters":float(p.distance_meters),"municipality":p.proposed_site.get("municipality"),"category":"hotels","geometry_status":"valid_point","media_status":"internal_unresolved_not_linked","selected_reason":"deterministic highest-safe candidate","rejected_reason":None,"safety_score":score_pilot_safety(p)} for p in rows]
    path=Path(output);path.mkdir(parents=True,exist_ok=True);(path/"accommodation_pilot_selection.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");return data
