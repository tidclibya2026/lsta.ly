from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceRecord:
    source_type: str
    source_id: str
    name_ar: str
    name_en: str | None
    latitude: float | None
    longitude: float | None
    municipality: str | None
    category_code: str | None
    description: str | None
    source_reference: str | None
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MatchCandidate:
    excel_id: str
    kml_id: str
    excel_name: str
    kml_name: str
    name_similarity: float
    distance_meters: float | None
    municipality_match: bool
    category_match: bool
    confidence_score: float
    decision: str
    conflict_fields: list[str]
