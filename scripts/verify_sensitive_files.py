import subprocess
import sys

tracked = subprocess.check_output(["git", "ls-files"], text=True, encoding="utf-8").splitlines()
bad = []
for path in tracked:
    low = path.lower()
    if low.endswith(".env") or low.startswith("data/raw/") or low.startswith(("reports/pilot/", "reports/merge/")) or low.endswith((".kml", ".kmz", ".xlsx", ".xls", ".dump", ".sql.gz")):
        bad.append(path)
if bad:
    print("Sensitive tracked files:", *bad, sep="\n")
    sys.exit(1)
print("Sensitive file guard passed")
