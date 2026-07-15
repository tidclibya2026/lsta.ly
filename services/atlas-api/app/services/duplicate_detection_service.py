from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DuplicateCandidate
from app.services.arabic_text_service import normalize_arabic_text


def compare_names(a: str | None, b: str | None) -> float: return round(SequenceMatcher(None, (a or "").casefold(), (b or "").casefold()).ratio() * 100, 2)
def compare_normalized_names(a: str | None, b: str | None) -> float: return compare_names(normalize_arabic_text(a or ""), normalize_arabic_text(b or ""))
def compare_descriptions(a: str | None, b: str | None) -> float: return compare_names(a, b)
def calculate_spatial_distance(distance_meters: float | None) -> float: return 100 if distance_meters is None else max(0, 100 - distance_meters / 10)
def compare_categories(a: str | None, b: str | None) -> bool: return bool(a and b and a == b)
def compare_municipalities(a: str | None, b: str | None) -> bool: return bool(a and b and a == b)
def calculate_duplicate_confidence(*, name_similarity: float, spatial_distance_meters: float | None, description_similarity: float = 0, category_match: bool = False, municipality_match: bool = False) -> float: return round(name_similarity * .4 + calculate_spatial_distance(spatial_distance_meters) * .3 + description_similarity * .15 + (10 if category_match else 0) + (5 if municipality_match else 0), 2)
def list_candidates(session: Session, status: str | None = None) -> list[DuplicateCandidate]:
    stmt = select(DuplicateCandidate).order_by(DuplicateCandidate.confidence_score.desc()); return list(session.scalars(stmt.where(DuplicateCandidate.status == status) if status else stmt))
def review_candidate(session: Session, candidate_id: UUID, decision: str, notes: str | None = None) -> DuplicateCandidate:
    item = session.get(DuplicateCandidate, candidate_id)
    if not item: raise LookupError("duplicate candidate not found")
    if decision == "merged": raise ValueError("actual merge is disabled")
    item.status, item.reviewer_notes = decision, notes; return item
def merge_preview(item: DuplicateCandidate) -> dict[str, Any]: return {"candidate_id": str(item.id), "operation": "preview_only", "source": {"type": item.source_entity_type, "id": item.source_entity_id}, "target": {"type": item.target_entity_type, "id": item.target_entity_id}, "confidence_score": float(item.confidence_score), "changes_applied": False}
def generate_candidates(session: Session) -> list[DuplicateCandidate]:
    # Deliberately conservative: current registry has one record, therefore no safe pair exists.
    return list_candidates(session)
