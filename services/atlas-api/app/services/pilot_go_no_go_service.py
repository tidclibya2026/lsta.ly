from datetime import datetime, timezone


def generate_go_no_go_decision(manifest, database_integrity, pilot_verification, rollback_count, security_ok):
    checks = {"backend": manifest.get("backend_failed") == 0, "frontend": manifest.get("frontend_failed") == 0, "ruff": manifest.get("ruff_status") == "passed", "typecheck": manifest.get("typecheck_status") == "passed", "build": manifest.get("build_status") == "passed", "migration": manifest.get("migration_heads") == 1, "database_integrity": database_integrity, "pilot_verification": pilot_verification, "rollback": rollback_count == 5, "security": security_ok}
    reasons = [key for key, value in checks.items() if not value]
    return {"go_no_go": "go" if not reasons else "no_go", "checks": checks, "reasons": reasons, "evaluated_at": datetime.now(timezone.utc).isoformat()}
