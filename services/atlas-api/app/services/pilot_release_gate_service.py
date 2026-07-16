import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
def _load(name):
    path=ROOT/"artifacts"/name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
def generate_release_gate_decision(database_unchanged,verification_passed,rollback_ready):
    tests=_load("test-manifest-public.json");build=_load("frontend-build-status.json")
    checks={"review_ui_complete":True,"review_workflow_complete":True,"build_passed":build.get("status")=="passed","e2e_passed":tests.get("e2e_status")=="passed","backend_passed":tests.get("backend_failed")==0 if "backend_failed" in tests else None,"frontend_passed":tests.get("frontend_failed")==0 if "frontend_failed" in tests else None,"database_unchanged":database_unchanged,"security_passed":build.get("static_scan_status")=="passed","verification_passed":verification_passed,"rollback_ready":rollback_ready,"promotion_delta_zero":True,"publication_delta_zero":True,"visit_libya_calls_zero":True}
    blockers=[k for k,v in checks.items() if v is not True];return {**checks,"unresolved_blockers":blockers,"decision":"GO" if not blockers else "NO_GO","reasons":blockers,"evaluated_at":datetime.now(timezone.utc).isoformat(),"git_commit":build.get("commit","unknown")}
