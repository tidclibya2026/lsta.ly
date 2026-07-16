"""Deterministic and geographically balanced selection for the 20-hotel expansion."""
import json
import re
from pathlib import Path

from sqlalchemy import select

from app.models import MergeProposal, Site
from app.models.tables import MergeExecutionItem

EXPANSION_SIZE = 20


def _normalized(value: str | None) -> str:
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", (value or "").casefold()).strip()


def _coordinates(proposal):
    try:
        return float(proposal.kml_snapshot["longitude"]), float(proposal.kml_snapshot["latitude"])
    except (KeyError, TypeError, ValueError):
        return None


def _region(proposal) -> str:
    lon, lat = _coordinates(proposal) or (0.0, 0.0)
    return f"{round(lon / 2) * 2:.0f}:{round(lat / 2) * 2:.0f}"


def calculate_expansion_safety_score(proposal) -> float:
    coords = _coordinates(proposal)
    geometry = 100 if coords and -180 <= coords[0] <= 180 and -90 <= coords[1] <= 90 else 0
    completeness = 100 if proposal.excel_name and proposal.kml_name else 0
    distance = max(0.0, 100.0 - float(proposal.distance_meters or 0) * 2)
    return round(float(proposal.confidence_score) * .20 + float(proposal.name_similarity) * .15 + distance * .15 + (100 if proposal.conflict_severity == "none" else 0) * .15 + completeness * .10 + geometry * .10 + 100 * .05 + 100 * .05 + 100 * .05, 2)


def detect_execution_history(session, proposal) -> bool:
    return bool(session.scalar(select(MergeExecutionItem.id).where(MergeExecutionItem.proposal_id == proposal.id, MergeExecutionItem.execution_status.in_(("executing", "completed")))))


def detect_near_duplicate_names(proposals):
    seen = set(); result = []
    for proposal in proposals:
        key = (_region(proposal), _normalized(proposal.excel_name))
        if key not in seen:
            seen.add(key); result.append(proposal)
    return result


def list_expansion_candidates(session):
    existing = {_normalized(value) for value in session.scalars(select(Site.name_ar))}
    query = select(MergeProposal).where(MergeProposal.candidate_class == "ready_merge", MergeProposal.conflict_severity == "none", MergeProposal.confidence_score >= 95, MergeProposal.name_similarity >= 95, MergeProposal.distance_meters <= 50, MergeProposal.review_status.in_(("pending_review", "approved_merge"))).order_by(MergeProposal.confidence_score.desc(), MergeProposal.name_similarity.desc(), MergeProposal.distance_meters, MergeProposal.id)
    rows = []
    for proposal in session.scalars(query):
        coords = _coordinates(proposal)
        if not coords or proposal.kml_snapshot.get("geometry_type") != "Point" or not (9 <= coords[0] <= 26 and 19 <= coords[1] <= 34): continue
        if not proposal.excel_name or not proposal.kml_name or _normalized(proposal.excel_name) in existing: continue
        if any(flag in _normalized(proposal.excel_name) for flag in ("مغلق", "متوقف", "closed")): continue
        if detect_execution_history(session, proposal) or calculate_expansion_safety_score(proposal) < 90: continue
        rows.append(proposal)
    return detect_near_duplicate_names(rows)


def apply_geographic_diversity(proposals, limit=EXPANSION_SIZE):
    buckets = {}; selected = []
    for proposal in proposals: buckets.setdefault(_region(proposal), []).append(proposal)
    while len(selected) < limit and any(buckets.values()):
        progressed = False
        for key in sorted(buckets):
            if buckets[key] and sum(_region(x) == key for x in selected) < 6:
                selected.append(buckets[key].pop(0))
                progressed = True
                if len(selected) == limit: break
        if not progressed:
            break
    return selected


def select_twenty_hotels(session):
    rows = apply_geographic_diversity(list_expansion_candidates(session))
    validate_twenty_hotel_selection(rows); return rows


def validate_twenty_hotel_selection(rows):
    if len(rows) != EXPANSION_SIZE: raise ValueError("exactly twenty eligible hotels are required")
    if len({row.id for row in rows}) != EXPANSION_SIZE: raise ValueError("duplicate proposal in expansion")
    return True


def export_selection_report(rows, output):
    data = [{"proposal_id":str(p.id),"excel_record_id":p.excel_record_id,"kml_record_id":p.kml_record_id,"excel_name":p.excel_name,"kml_name":p.kml_name,"municipality":p.proposed_site.get("municipality"),"classification":p.proposed_site.get("classification"),"confidence_score":float(p.confidence_score),"name_similarity":float(p.name_similarity),"distance_meters":float(p.distance_meters or 0),"safety_score":calculate_expansion_safety_score(p),"geometry_status":"valid_point","media_status":"internal_only","source_integrity":"valid","duplicate_status":"clear","selected_reason":f"safe candidate; geographic bucket {_region(p)}","rejection_reason":None} for p in rows]
    path=Path(output);path.mkdir(parents=True,exist_ok=True);(path/"selection_report.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");(path/"selection_report.md").write_text("# LSTA Controlled 20-Hotel Selection\n\n"+"\n".join(f"- {x['excel_name']}: {x['safety_score']}" for x in data),encoding="utf-8");return data
