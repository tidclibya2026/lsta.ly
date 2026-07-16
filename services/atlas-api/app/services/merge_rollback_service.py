from app.models import Site


def build_restore_plan(item):
    return {"site_id": str(item.target_site_id) if item.target_site_id else None, "snapshot": item.pre_merge_snapshot, "restores": ["site", "geometry", "attributes", "media", "quality"], "preserves": ["audit", "lineage"]}
def validate_rollback(item): return {"valid": item.execution_status == "completed" and bool(item.pre_merge_snapshot), "reasons": [] if item.pre_merge_snapshot else ["missing_pre_merge_snapshot"]}
def preview_rollback(item): return {"validation": validate_rollback(item), "restore_plan": build_restore_plan(item), "writes": 0}
def execute_rollback(session,item,allow=False):
    if not allow: raise PermissionError("actual rollback disabled outside controlled tests")
    result=validate_rollback(item)
    if not result["valid"]: raise ValueError(result["reasons"])
    site=session.get(Site,item.target_site_id)
    for key in ("name_ar","name_en","description"): 
        if key in item.pre_merge_snapshot: setattr(site,key,item.pre_merge_snapshot[key])
    item.execution_status="rolled_back"; return site
def record_rollback_event(*args, **kwargs): return None
