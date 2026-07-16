import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4];ART=ROOT/"artifacts"
FILES={"backend":"backend-test-status.json","frontend":"frontend-build-status.json","merge_engine":"merge-engine-test-status.json","e2e":"pilot-e2e-status.json","migration":"migration-status.json","security":"security-status.json","database_integrity":"development-db-integrity.json"}
def _head():
    try:return subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
    except Exception:return "unknown"
def evaluate_release_gate():
    head=_head();states={};reasons=[]
    for key,name in FILES.items():
        path=ART/name
        if not path.exists():states[key]="unknown"
        else:
            value=json.loads(path.read_text(encoding="utf-8"));states[key]="passed"if value.get("status")=="passed"and value.get("git_commit")==head else("failed"if value.get("status")=="failed"else"unknown")
        if states[key]!="passed":reasons.append(f"{key}:{states[key]}")
    return {"decision":"GO"if not reasons else"NO_GO",**states,"build":states["frontend"],"reasons":reasons,"git_commit":head,"evaluated_at":datetime.now(timezone.utc).isoformat()}
def generate_release_gate_decision(*_):return evaluate_release_gate()
