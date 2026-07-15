from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_manifest(output: Path, items: list[dict[str, Any]]) -> Path:
    path = output / "media_manifest.json"
    payload = {
        "project": "LSTA",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_count": len(items),
        "assets": items,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
