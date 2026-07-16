"""Idempotent import of merge-engine previews into the staging review workspace."""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import MergeBatch, MergeProposal

LOGGER = logging.getLogger("lsta.merge_import")
ENGINE_VERSION = "1.0.0"


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Required input is missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_batch_code(entity_type: str, excel_sha256: str, kml_sha256: str, engine_version: str = ENGINE_VERSION) -> str:
    identity = f"{entity_type}:{excel_sha256}:{kml_sha256}:{engine_version}".encode()
    return f"LSTA-MERGE-{entity_type.upper()}-{hashlib.sha256(identity).hexdigest()[:16]}"


def _snapshot(source: dict[str, Any], *, kml: bool = False) -> dict[str, Any]:
    allowed = {"source_id", "name_ar", "name_en", "municipality", "category_code", "latitude", "longitude", "description", "source_reference"}
    result = {key: source.get(key) for key in allowed if source.get(key) not in (None, "")}
    props = source.get("properties") if isinstance(source.get("properties"), dict) else {}
    if kml:
        result["images"] = props.get("local_media_urls") or props.get("image_urls") or []
        result["rights_status"] = props.get("rights_status", "unknown")
        result["folder_name"] = props.get("folder_name")
        result["geometry_type"] = props.get("geometry_type")
        result["spatial_description"] = props.get("description_text") or source.get("description")
    else:
        safe_business_keys = {"عدد الغرف", "عدد الأسرة", "الطاقة الاستيعابية", "الهاتف", "العنوان/الموقع", "التصنيف الفرعي", "درجة الجودة", "حالة التحقق", "أولوية التحقق"}
        result["business_attributes"] = {key: value for key, value in props.items() if key in safe_business_keys and value not in (None, "")}
    return result


def normalize_preview_item(item: dict[str, Any]) -> dict[str, Any]:
    match, conflicts = item.get("match") or {}, item.get("conflicts") or {}
    excel, kml = item.get("excel_source") or {}, item.get("kml_source") or {}
    excel_id, kml_id = str(item.get("excel_record_id") or "").strip(), str(item.get("kml_record_id") or "").strip()
    if not excel_id or not kml_id:
        raise ValueError("Both excel_record_id and kml_record_id are required")
    candidate = str(match.get("decision") or "possible_match")
    severity = str(conflicts.get("severity") or "none")
    if candidate not in {"ready_merge", "needs_review", "possible_match"}:
        raise ValueError(f"Unsupported candidate class: {candidate}")
    if severity not in {"none", "medium", "high"}:
        raise ValueError(f"Unsupported conflict severity: {severity}")
    priority = "low" if candidate == "ready_merge" and severity == "none" else "high" if severity == "high" else "normal"
    assigned = "data_manager" if severity == "high" else "gis_specialist" if severity == "medium" else "reviewer"
    return {"excel_record_id": excel_id, "kml_record_id": kml_id, "excel_name": excel.get("name_ar") or excel.get("name_en"), "kml_name": kml.get("name_ar") or kml.get("name_en"), "confidence_score": float(match.get("confidence_score") or 0), "name_similarity": float(match.get("name_similarity") or 0), "distance_meters": match.get("distance_meters"), "candidate_class": candidate, "conflict_severity": severity, "conflict_fields": conflicts.get("items") if isinstance(conflicts.get("items"), list) else [], "excel_snapshot": _snapshot(excel), "kml_snapshot": _snapshot(kml, kml=True), "proposed_site": item.get("proposed_site") or {}, "field_sources": item.get("field_sources") or {}, "review_status": "pending_review", "priority": priority, "assigned_role": assigned}


def import_merge_proposals(session: Session, *, excel_path: Path, kml_path: Path, summary_path: Path, preview_path: Path, entity_type: str = "hotels", created_by: str = "system_import") -> dict[str, Any]:
    paths = [Path(value) for value in (excel_path, kml_path, summary_path, preview_path)]
    excel_path, kml_path, summary_path, preview_path = paths
    excel_sha, kml_sha = calculate_sha256(excel_path), calculate_sha256(kml_path)
    summary, previews = load_json(summary_path), load_json(preview_path)
    if not isinstance(summary, dict) or not isinstance(previews, list):
        raise ValueError("Summary must be an object and preview must be an array")
    code = build_batch_code(entity_type, excel_sha, kml_sha)
    invalid_items: list[dict[str, Any]] = []
    try:
        batch = session.scalar(select(MergeBatch).where(MergeBatch.batch_code == code))
        created = batch is None
        if batch is None:
            batch = MergeBatch(batch_code=code, entity_type=entity_type, excel_file_name=excel_path.name, excel_sha256=excel_sha, kml_file_name=kml_path.name, kml_sha256=kml_sha, excel_record_count=int(summary.get("excel_records", 0)), kml_record_count=int(summary.get("kml_records", 0)), raw_candidate_count=int(summary.get("raw_candidate_pairs", 0)), proposal_count=0, engine_version=ENGINE_VERSION, matching_parameters={"min_score": summary.get("min_score"), "max_distance_meters": summary.get("max_distance_meters"), "one_to_one": True, "automatic_merge": False}, status="ready_for_review", created_by=created_by)
            session.add(batch); session.flush()
        inserted = duplicates = 0
        for index, raw in enumerate(previews):
            try:
                proposal = normalize_preview_item(raw)
            except (TypeError, ValueError) as exc:
                invalid_items.append({"index": index, "reason": str(exc)}); continue
            statement = insert(MergeProposal).values(batch_id=batch.id, **proposal).on_conflict_do_nothing(constraint="uq_merge_proposal_pair").returning(MergeProposal.id)
            if session.scalar(statement) is None: duplicates += 1
            else: inserted += 1
        batch.proposal_count = int(session.scalar(select(func.count()).select_from(MergeProposal).where(MergeProposal.batch_id == batch.id)) or 0)
        session.commit()
    except Exception:
        session.rollback(); LOGGER.exception("Merge proposal import rolled back", extra={"entity_type": entity_type}); raise
    pending = int(session.scalar(select(func.count()).select_from(MergeProposal).where(MergeProposal.batch_id == batch.id, MergeProposal.review_status == "pending_review")) or 0)
    return {"status": "success_without_merge", "batch_id": str(batch.id), "batch_code": code, "batch_created": created, "inserted": inserted, "duplicates": duplicates, "invalid": len(invalid_items), "invalid_items": invalid_items[:20], "total": batch.proposal_count, "pending": pending, "national_site_writes": 0, "promotions": 0}
