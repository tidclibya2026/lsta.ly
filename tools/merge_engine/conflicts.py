from __future__ import annotations

from dataclasses import dataclass

from tools.merge_engine.models import SourceRecord
from tools.merge_engine.scoring import distance_meters, name_similarity


@dataclass(slots=True)
class ConflictResult:
    conflict_types: list[str]
    severity: str
    requires_manual_review: bool


def detect_conflicts(
    excel_record: SourceRecord,
    kml_record: SourceRecord,
) -> ConflictResult:
    conflicts: list[str] = []

    excel_name = excel_record.name_ar or excel_record.name_en or ""
    kml_name = kml_record.name_ar or kml_record.name_en or ""

    name_score = name_similarity(excel_name, kml_name)
    distance = distance_meters(excel_record, kml_record)

    if name_score < 70:
        conflicts.append("name_conflict")

    if distance is None:
        conflicts.append("missing_coordinates")
    elif distance > 500:
        conflicts.append("spatial_conflict")
    elif distance > 100:
        conflicts.append("spatial_warning")

    if (
        excel_record.municipality
        and kml_record.municipality
        and excel_record.municipality.strip()
        != kml_record.municipality.strip()
    ):
        conflicts.append("municipality_conflict")

    if (
        excel_record.category_code
        and kml_record.category_code
        and excel_record.category_code.strip()
        != kml_record.category_code.strip()
    ):
        conflicts.append("category_conflict")

    if any(
        item in conflicts
        for item in (
            "name_conflict",
            "spatial_conflict",
            "municipality_conflict",
            "category_conflict",
        )
    ):
        severity = "high"
    elif conflicts:
        severity = "medium"
    else:
        severity = "none"

    return ConflictResult(
        conflict_types=conflicts,
        severity=severity,
        requires_manual_review=severity in {"high", "medium"},
    )