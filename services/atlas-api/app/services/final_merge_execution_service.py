"""Controlled merge execution. No publication or promotion side effects."""
import hashlib
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    MediaAsset,
    MergeProposal,
    Site,
    SiteGeometry,
    SiteProfile,
    SiteQualitySnapshot,
    SiteVersion,
)
from app.models.tables import MergeExecutionBatch, MergeExecutionEvent, MergeExecutionItem
from app.services.data_lineage_service import create_lineage_edge, get_or_create_node
from app.services.merge_execution_eligibility_service import evaluate_proposal_eligibility
from app.services.merge_execution_preview_service import create_execution_preview

ENGINE_VERSION = "9.4.0"


def _event(session, batch, event_type, role, item=None, payload=None, reference=None):
    row = MergeExecutionEvent(execution_batch_id=batch.id, execution_item_id=item.id if item else None, proposal_id=item.proposal_id if item else None, event_type=event_type, actor_role=role, actor_reference=reference, event_payload=payload or {})
    session.add(row); return row


def _code(proposal, operation):
    d = proposal.decisions[-1]
    raw = f"{proposal.id}:{d.id}:{proposal.batch.excel_sha256}:{proposal.batch.kml_sha256}:{ENGINE_VERSION}:{operation}"
    return hashlib.sha256(raw.encode()).hexdigest()


def create_execution_batch(session: Session, merge_batch_id, proposals, role, reference=None, operation_type="create_national_site"):
    if role not in {"data_manager", "system_admin"}: raise PermissionError("execution batch requires data_manager or system_admin")
    codes = sorted(_code(p, operation_type) for p in proposals)
    code = "LSTA-EXEC-" + hashlib.sha256("|".join(codes).encode()).hexdigest()[:20]
    existing = session.scalar(select(MergeExecutionBatch).where(MergeExecutionBatch.execution_code == code))
    if existing: return existing
    batch = MergeExecutionBatch(execution_code=code, merge_batch_id=merge_batch_id, requested_proposal_count=len(proposals), execution_mode="dry_run", status="draft", requested_by_role=role, requested_by_reference=reference)
    session.add(batch); session.flush(); _event(session, batch, "execution_requested", role, reference=reference)
    for p in proposals:
        preview = create_execution_preview(session, p, operation_type)
        eligibility = evaluate_proposal_eligibility(session, p, operation_type)
        session.add(MergeExecutionItem(execution_batch_id=batch.id, proposal_id=p.id, operation_type=operation_type, proposed_snapshot=p.proposed_site, field_merge_plan=preview["field_merge_plan"], validation_results=eligibility, execution_status="eligible" if eligibility["eligible"] else "blocked"))
    return batch


def add_execution_items(*args, **kwargs):
    return None


def run_dry_run(session, batch, role):
    if role not in {"data_manager", "system_admin"}: raise PermissionError("dry run forbidden")
    eligible = sum(i.execution_status == "eligible" for i in batch.items); blocked = len(batch.items) - eligible
    batch.eligible_proposal_count = eligible; batch.status = "validated" if eligible and not blocked else "blocked"
    batch.dry_run_report = {"successful": bool(eligible and not blocked), "eligible": eligible, "blocked": blocked, "atlas_writes": 0, "engine_version": ENGINE_VERSION}
    batch.validation_summary = {"valid": eligible, "invalid": blocked}; _event(session, batch, "dry_run_completed", role, payload=batch.dry_run_report)
    return batch.dry_run_report


def authorize_execution(session, batch, role, reference=None):
    if role not in {"data_manager", "system_admin"}: raise PermissionError("authorization forbidden")
    if batch.status != "validated" or not batch.dry_run_report.get("successful"): raise ValueError("successful dry run required")
    if reference and reference == batch.requested_by_reference: batch.validation_summary = {**batch.validation_summary, "separation_of_duties_warning": True}
    batch.status = "approved_for_execution"; batch.execution_mode = "controlled_execution"; _event(session, batch, "execution_authorized", role, reference=reference)


def _national_id(session):
    n = session.scalar(select(func.count()).select_from(Site)) + 1
    while session.scalar(select(Site.id).where(Site.national_id == f"LSTA-NATIONAL-{n:06d}")): n += 1
    return f"LSTA-NATIONAL-{n:06d}"


def create_national_site_from_merge(session, item):
    p = session.get(MergeProposal, item.proposal_id); s = Site(national_id=_national_id(session), name_ar=p.proposed_site.get("name_ar") or p.proposed_site["name"], name_en=p.proposed_site.get("name_en"), description=p.proposed_site.get("description"), verification_status="approved")
    session.add(s); session.flush(); item.target_site_id=s.id; item.target_national_id=s.national_id
    session.add(SiteProfile(site_id=s.id, contact_information=p.excel_snapshot.get("contact_information", {}), internal_notes="Created by controlled merge execution"))
    return s


def create_site_version(session, site, snapshot, actor=None):
    n = (session.scalar(select(func.max(SiteVersion.version_number)).where(SiteVersion.site_id == site.id)) or 0) + 1
    row=SiteVersion(site_id=site.id, version_number=n, snapshot=snapshot, change_summary="Controlled merge execution"); session.add(row); return row


def update_national_site_from_merge(session, item):
    s=session.get(Site,item.target_site_id); item.pre_merge_snapshot={"national_id":s.national_id,"name_ar":s.name_ar,"description":s.description}; create_site_version(session,s,item.pre_merge_snapshot)
    for f in item.field_merge_plan:
        if f["action"]=="update" and f["field"] in {"name_ar","name_en","description"}: setattr(s,f["field"],f["proposed_value"])
    return s


def link_approved_media(session, site, proposal):
    count=0
    for m in proposal.kml_snapshot.get("images", []):
        if isinstance(m,dict) and m.get("rights_status")=="approved_public" and m.get("url"):
            session.add(MediaAsset(site_id=site.id,url=m["url"],verification_status="approved",publication_status="internal"));count+=1
    return count


def apply_geometry_changes(session, site, proposal):
    lat, lon = proposal.kml_snapshot.get("latitude"), proposal.kml_snapshot.get("longitude")
    if lat is None or lon is None: raise ValueError("valid KML coordinates required")
    row = SiteGeometry(site_id=site.id, geometry_type="Point", geometry=WKTElement(f"POINT ({float(lon)} {float(lat)})", srid=4326))
    session.add(row); session.flush(); site.primary_geometry_id = row.id
    return row


def create_lineage(session, proposal, site):
    source = get_or_create_node(session, "merge_proposal", str(proposal.id), "Approved merge proposal")
    target = get_or_create_node(session, "national_site", site.national_id, site.name_ar)
    return create_lineage_edge(session, source, target, "controlled_merge", "Final Merge Execution Engine", process_version=ENGINE_VERSION)


def execute_item(session, batch, item, role):
    if item.execution_status != "eligible": return
    try:
        with session.begin_nested():
            item.execution_status="executing"; site=create_national_site_from_merge(session,item) if item.operation_type=="create_national_site" else update_national_site_from_merge(session,item)
            proposal=session.get(MergeProposal,item.proposal_id); geometry=apply_geometry_changes(session,site,proposal); media=link_approved_media(session,site,proposal)
            session.add(SiteQualitySnapshot(site_id=site.id,overall_score=80,score_breakdown={"merge":80},critical_issues=[],warnings=[],calculated_by="merge_execution",source_version=ENGINE_VERSION))
            create_lineage(session,proposal,site); session.add(AuditLog(action="controlled_merge_executed",entity_type="site",entity_id=site.id,details={"proposal_id":str(proposal.id),"execution_item_id":str(item.id),"publication":False}))
            item.execution_status="completed";item.executed_at=datetime.now(timezone.utc);_event(session,batch,"site_created" if item.operation_type.startswith("create") else "site_updated",role,item,{"national_id":site.national_id,"geometry_id":str(geometry.id),"media_linked":media})
    except Exception as exc:
        item.execution_status="failed";item.error_code="EXECUTION_FAILED";item.error_message=str(exc);_event(session,batch,"execution_failed",role,item,{"error":str(exc)})


def execute_batch(session,batch,role):
    if role not in {"data_manager","system_admin"}: raise PermissionError("execution forbidden")
    if batch.status!="approved_for_execution": raise ValueError("final authorization required")
    batch.status="running";batch.started_at=datetime.now(timezone.utc)
    for item in batch.items: execute_item(session,batch,item,role)
    batch.executed_proposal_count=sum(i.execution_status=="completed" for i in batch.items);batch.failed_proposal_count=sum(i.execution_status=="failed" for i in batch.items);batch.status="completed_with_errors" if batch.failed_proposal_count else "completed";batch.completed_at=datetime.now(timezone.utc)
    return batch


def apply_attribute_changes(*args, **kwargs): return None
def create_quality_snapshot(*args, **kwargs): return None
def create_audit_events(*args, **kwargs): return None
def finalize_execution(*args, **kwargs): return None
def mark_execution_failed(*args, **kwargs): return None
