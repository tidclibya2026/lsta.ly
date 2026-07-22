"""Portable synthetic merge inputs used when sensitive source files are unavailable."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import gettempdir


def merge_input_paths() -> dict[str, Path]:
    directory = Path(gettempdir()) / "lsta-pytest-merge-inputs"
    directory.mkdir(parents=True, exist_ok=True)
    excel = directory / "hotels.xlsx"
    kml = directory / "hotels.kml"
    summary = directory / "summary.json"
    preview = directory / "preview.json"
    excel.write_bytes(b"LSTA synthetic Excel identity")
    kml.write_text("<kml><!-- LSTA synthetic identity --></kml>", encoding="utf-8")
    summary.write_text(
        json.dumps({"excel_records": 457, "kml_records": 457, "raw_candidate_pairs": 457}),
        encoding="utf-8",
    )
    rows = []
    for index in range(457):
        ready = index < 433
        high = 433 <= index < 442
        rows.append(
            {
                "excel_record_id": f"EXCEL-{index:06d}",
                "kml_record_id": f"KML-{index:06d}",
                "match": {
                    "decision": "ready_merge" if ready else "needs_review",
                    "confidence_score": 100 if ready else 80,
                    "name_similarity": 100 if ready else 80,
                    "distance_meters": 0,
                },
                "conflicts": {"severity": "none" if ready else "high" if high else "medium", "items": []},
                "excel_source": {"name_ar": f"فندق اختباري {index}"},
                "kml_source": {
                    "name_ar": f"فندق اختباري {index}",
                    "latitude": 32.8,
                    "longitude": 13.2,
                    "properties": {"geometry_type": "Point", "rights_status": "unknown"},
                },
                "proposed_site": {"name_ar": f"فندق اختباري {index}"},
                "field_sources": {"name_ar": "excel", "geometry": "kml"},
            }
        )
    preview.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return {"excel_path": excel, "kml_path": kml, "summary_path": summary, "preview_path": preview}
