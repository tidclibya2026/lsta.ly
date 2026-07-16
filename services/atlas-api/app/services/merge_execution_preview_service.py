"""Read-only preview construction; never flushes or commits atlas rows."""
from sqlalchemy import func, select

from app.models import Site, SiteVersion
from app.services.merge_field_policy_service import build_field_merge_plan


def generate_pre_merge_snapshot(session, site_id):
    if not site_id: return {}
    site = session.get(Site, site_id)
    return {} if not site else {"id": str(site.id), "national_id": site.national_id, "name_ar": site.name_ar, "description": site.description, "verification_status": site.verification_status}


def create_execution_preview(session, proposal, operation_type, target_site_id=None):
    current = generate_pre_merge_snapshot(session, target_site_id)
    plan = build_field_merge_plan(current, proposal.proposed_site, proposal.field_sources)
    return {"proposal_id": str(proposal.id), "operation_type": operation_type, "target_site": current or None, "field_merge_plan": plan,
        "change_summary": {"updates": sum(x["action"] == "update" for x in plan), "skipped": sum(x["action"] == "skip" for x in plan)},
        "geometry": {"current": None, "proposed": proposal.kml_snapshot.get("geometry"), "distance_meters": float(proposal.distance_meters) if proposal.distance_meters is not None else None},
        "media": [x for x in proposal.kml_snapshot.get("images", []) if isinstance(x, dict) and x.get("rights_status") == "approved_public"],
        "warnings": [x for x in plan if x["action"] in {"skip", "conflict"}], "lineage": ["merge_proposal", "national_site"],
        "previous_versions": session.scalar(select(func.count()).select_from(SiteVersion).where(SiteVersion.site_id == target_site_id)) if target_site_id else 0}


def compare_current_and_proposed(current, proposed):
    return {k: {"current": current.get(k), "proposed": v} for k, v in proposed.items() if current.get(k) != v}

def calculate_change_summary(plan): return {"updates": sum(x["action"] == "update" for x in plan)}
def generate_proposed_snapshot(proposal): return dict(proposal.proposed_site)
def validate_preview_integrity(preview): return bool(preview.get("proposal_id") and preview.get("field_merge_plan") is not None)
def get_execution_preview(item): return {"id": str(item.id), "proposed_snapshot": item.proposed_snapshot, "field_merge_plan": item.field_merge_plan, "validation_results": item.validation_results}
