from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ImportBatch, ImportFeature

QUALITY_WEIGHTS = {
    "arabic_name": 15,
    "description": 15,
    "valid_geometry": 20,
    "documented_source": 10,
    "has_image": 15,
    "category": 10,
    "municipality": 10,
    "no_critical_issues": 5,
}


def calculate_quality(session: Session, feature: ImportFeature) -> dict[str, Any]:
    properties = feature.properties or {}
    issues = [str(issue) for issue in (feature.validation_issues or [])]
    lowered = [issue.lower() for issue in issues]
    critical = [
        issue
        for issue, value in zip(issues, lowered, strict=True)
        if value.startswith("critical") or "invalid_geometry" in value or "invalid_coordinate" in value
    ]
    extended = properties.get("extended_data") or {}
    checks = {
        "arabic_name": bool(feature.name_ar and feature.name_ar.strip()),
        "description": bool(properties.get("description_text") or properties.get("description_html")),
        "valid_geometry": bool(session.scalar(select(func.ST_IsValid(feature.geometry)))),
        "documented_source": bool(session.get(ImportBatch, feature.batch_id))
        and bool(properties.get("source_sha256") or properties.get("source_id")),
        "has_image": bool(properties.get("image_urls") or []),
        "category": bool(feature.proposed_category_code or extended.get("النوع") or properties.get("category")),
        "municipality": bool(feature.proposed_municipality_code or properties.get("municipality_code")),
        "no_critical_issues": not critical,
    }
    breakdown = {
        key: {"earned": QUALITY_WEIGHTS[key] if passed else 0, "weight": QUALITY_WEIGHTS[key], "passed": passed}
        for key, passed in checks.items()
    }
    warnings = [issue for issue in issues if issue not in critical]
    if not checks["municipality"]:
        warnings.append("missing_municipality")
    if not checks["category"]:
        warnings.append("missing_category")
    return {
        "quality_score": sum(item["earned"] for item in breakdown.values()),
        "quality_breakdown": breakdown,
        "critical_issues": critical,
        "warnings": list(dict.fromkeys(warnings)),
    }
