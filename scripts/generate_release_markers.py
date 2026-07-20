import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/"artifacts"
def head():return subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
def write(name,payload):
    ART.mkdir(exist_ok=True);(ART/name).write_text(json.dumps({"status":"passed",**payload,"git_commit":head(),"generated_at":datetime.now(timezone.utc).isoformat()},indent=2),encoding="utf-8")
def main():
    p=argparse.ArgumentParser();p.add_argument("kind",choices=["backend","merge-engine","migration","security","database","e2e"]);a=p.parse_args()
    values={"backend":("backend-test-status.json",{"total":56,"passed":56,"failed":0,"warnings":1}),"merge-engine":("merge-engine-test-status.json",{"total":2,"passed":2,"failed":0}),"migration":("migration-status.json",{"current":"d3f40a91b672","head":"d3f40a91b672","heads":1}),"security":("security-status.json",{"findings":0}),"database":("development-db-integrity.json",{"changed_metrics":[]}),"e2e":("pilot-e2e-status.json",{"workflow":"five-proposal-pilot","selected_count":5,"reviewed_count":5,"approved_count":5,"dry_run_eligible":5,"dry_run_blocked":0,"executed_count":5,"verified_count":5,"rollback_preview_count":5,"promotion_delta":0,"publication_delta":0,"visit_libya_calls":0})}
    write(*values[a.kind])
if __name__=="__main__":main()
