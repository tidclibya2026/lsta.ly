from __future__ import annotations

from typing import Any

from tools.merge_engine.conflicts import detect_conflicts
from tools.merge_engine.models import SourceRecord


def build_merge_preview(
    excel_record: SourceRecord,
    kml_record: SourceRecord,
    total_score: float,
    name_score: float,
    distance_meters_value: float | None,
) -> dict[str, Any]:
    conflicts = detect_conflicts(excel_record, kml_record)

    return {
        "excel_record_id": excel_record.record_id,
        "kml_record_id": kml_record.record_id,
        "match_score": total_score,
        "name_score": name_score,
        "distance_meters": distance_meters_value,
        "conflicts": conflicts.conflict_types,
        "conflict_severity": conflicts.severity,
        "requires_manual_review": conflicts.requires_manual_review,
        "proposed_site": {
            "name_ar": (
                excel_record.name_ar
                or kml_record.name_ar
            ),
            "name_en": (
                excel_record.name_en
                or kml_record.name_en
            ),
            "municipality": (
                excel_record.municipality
                or kml_record.municipality
            ),
            "category_code": (
                excel_record.category_code
                or kml_record.category_code
            ),
            "latitude": kml_record.latitude,
            "longitude": kml_record.longitude,
        },
        "field_sources": {
            "geometry": "kml",
            "coordinates": "kml",
            "photos": "kml",
            "name_ar": "excel_preferred",
            "name_en": "excel_preferred",
            "municipality": "excel_preferred",
            "category_code": "excel_preferred",
            "business_attributes": "excel",
        },
        "decision": "pending_review",
        "reviewer_notes": "",
    }