from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SearchIndexStatus
from app.services.arabic_text_service import normalize_arabic_text, normalize_english_text

INDEX_VERSION = "postgres-v1"


def _document(entity_type: str, entity_id: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"entity_type": entity_type, "entity_id": entity_id, "national_id": values.get("national_id"), "name_ar": values.get("name_ar"), "name_en": values.get("name_en"), "normalized_name_ar": normalize_arabic_text(values.get("name_ar") or ""), "normalized_name_en": normalize_english_text(values.get("name_en") or ""), "description_text": values.get("description_text"), "category": values.get("category"), "municipality": values.get("municipality"), "geometry_type": values.get("geometry_type"), "verification_status": values.get("verification_status"), "publication_status": values.get("publication_status"), "review_status": values.get("review_status"), "quality_score": values.get("quality_score"), "completeness_score": values.get("completeness_score"), "has_images": bool(values.get("has_images")), "has_documents": bool(values.get("has_documents")), "metadata_keywords": values.get("metadata_keywords") or [], "source_reference": values.get("source_reference"), "centroid": values.get("centroid"), "bbox": values.get("bbox"), "updated_at": values.get("updated_at")}


def _index(session: Session, entity_type: str, entity_id: str, values: dict[str, Any]) -> dict[str, Any]:
    status = session.scalar(select(SearchIndexStatus).where(SearchIndexStatus.entity_type == entity_type, SearchIndexStatus.entity_id == entity_id, SearchIndexStatus.index_version == INDEX_VERSION))
    if not status: status = SearchIndexStatus(entity_type=entity_type, entity_id=entity_id, index_version=INDEX_VERSION); session.add(status)
    status.status, status.indexed_at, status.error_message = "indexed", datetime.now(timezone.utc), None
    return _document(entity_type, entity_id, values)


def index_registry_site(session: Session, entity_id: str, values: dict[str, Any]) -> dict[str, Any]: return _index(session, "registry", entity_id, values)
def index_staging_feature(session: Session, entity_id: str, values: dict[str, Any]) -> dict[str, Any]: return _index(session, "staging", entity_id, values)
def index_metadata_entry(session: Session, entity_id: str, values: dict[str, Any]) -> dict[str, Any]: return _index(session, "metadata", entity_id, values)
def index_media_review_item(session: Session, entity_id: str, values: dict[str, Any]) -> dict[str, Any]: return _index(session, "media", entity_id, values)
def rebuild_search_index(session: Session) -> int:
    count = session.query(SearchIndexStatus).update({SearchIndexStatus.status: "stale"}); session.flush(); return count
def mark_index_stale(session: Session, entity_type: str, entity_id: str) -> int: return session.query(SearchIndexStatus).filter_by(entity_type=entity_type, entity_id=entity_id).update({SearchIndexStatus.status: "stale"})
def get_index_status(session: Session) -> list[SearchIndexStatus]: return list(session.scalars(select(SearchIndexStatus)))
def validate_index_integrity(session: Session) -> dict[str, int]:
    rows = get_index_status(session); return {state: sum(row.status == state for row in rows) for state in ("pending", "indexed", "failed", "stale")}
