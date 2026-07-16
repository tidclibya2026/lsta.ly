from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tools.merge_engine.models import MatchCandidate, SourceRecord
from tools.merge_engine.readers import read_configured_excel, read_geojson, read_hotels_excel
from tools.merge_engine.scoring import score_pair
from tools.merge_engine.text_normalizer import normalize_text


def _decision(
    score: float,
    name_score: float,
    distance: float | None,
) -> str:
    """
    يصنف مرشح المطابقة دون تنفيذ أي دمج فعلي.

    ready_merge:
        مرشح قوي وجاهز لمراجعة سريعة، وليس دمجًا تلقائيًا.

    needs_review:
        مرشح جيد يحتاج مراجعة الاسم والإحداثيات.

    possible_match:
        مرشح محتمل يحتاج مراجعة يدوية كاملة.

    no_match:
        لا يحقق الحد الأدنى المطلوب.
    """
    if (
        score >= 92.0
        and name_score >= 90.0
        and distance is not None
        and distance <= 100.0
    ):
        return "ready_merge"

    if (
        score >= 80.0
        and name_score >= 75.0
        and distance is not None
        and distance <= 500.0
    ):
        return "needs_review"

    if score >= 65.0:
        return "possible_match"

    return "no_match"


def _normalized_equal(
    first: str | None,
    second: str | None,
) -> bool:
    if not first or not second:
        return False

    return normalize_text(first) == normalize_text(second)


def _detect_conflicts(
    excel: SourceRecord,
    kml: SourceRecord,
    name_score: float,
    distance: float | None,
) -> list[str]:
    """
    يكشف التعارضات بين المرجع الوصفي Excel والمرجع المكاني KML.
    """
    conflicts: list[str] = []

    if name_score < 70.0:
        conflicts.append("name_conflict")
    elif name_score < 85.0:
        conflicts.append("name_warning")

    if distance is None:
        conflicts.append("missing_coordinates")
    elif distance > 500.0:
        conflicts.append("spatial_conflict")
    elif distance > 100.0:
        conflicts.append("spatial_warning")

    if (
        excel.municipality
        and kml.municipality
        and not _normalized_equal(
            excel.municipality,
            kml.municipality,
        )
    ):
        conflicts.append("municipality_conflict")

    if (
        excel.category_code
        and kml.category_code
        and not _normalized_equal(
            excel.category_code,
            kml.category_code,
        )
    ):
        conflicts.append("category_conflict")

    return conflicts


def _conflict_severity(conflicts: list[str]) -> str:
    high_conflicts = {
        "name_conflict",
        "spatial_conflict",
        "municipality_conflict",
        "category_conflict",
    }

    if any(item in high_conflicts for item in conflicts):
        return "high"

    if conflicts:
        return "medium"

    return "none"


def _candidate_sort_key(
    candidate: MatchCandidate,
) -> tuple[float, float, float]:
    """
    يرتب المرشحين حسب:
    1. أعلى درجة ثقة.
    2. أعلى تشابه اسم.
    3. أقصر مسافة.
    """
    distance = (
        candidate.distance_meters
        if candidate.distance_meters is not None
        else float("inf")
    )

    return (
        -candidate.confidence_score,
        -candidate.name_similarity,
        distance,
    )


def _build_all_candidates(
    excel_rows: list[SourceRecord],
    kml_rows: list[SourceRecord],
    min_score: float,
    max_distance: float,
) -> list[MatchCandidate]:
    """
    ينشئ جميع المرشحين المقبولين مبدئيًا.

    لا يطبق المطابقة واحد إلى واحد في هذه المرحلة.
    """
    candidates: list[MatchCandidate] = []

    for excel in excel_rows:
        for kml in kml_rows:
            (
                score,
                name_score,
                distance,
                municipality_match,
                category_match,
            ) = score_pair(excel, kml)

            if distance is not None and distance > max_distance:
                continue

            if score < min_score:
                continue

            conflicts = _detect_conflicts(
                excel=excel,
                kml=kml,
                name_score=name_score,
                distance=distance,
            )

            candidates.append(
                MatchCandidate(
                    excel_id=excel.source_id,
                    kml_id=kml.source_id,
                    excel_name=excel.name_ar or excel.name_en or "",
                    kml_name=kml.name_ar or kml.name_en or "",
                    name_similarity=name_score,
                    distance_meters=distance,
                    municipality_match=municipality_match,
                    category_match=category_match,
                    confidence_score=score,
                    decision=_decision(
                        score=score,
                        name_score=name_score,
                        distance=distance,
                    ),
                    conflict_fields=conflicts,
                )
            )

    return candidates


def _enforce_one_to_one(
    candidates: list[MatchCandidate],
) -> tuple[
    list[MatchCandidate],
    list[dict[str, Any]],
]:
    """
    يطبق مطابقة واحد إلى واحد بطريقة تحفظية.

    لا يسمح:
    - لسجل Excel بالارتباط بأكثر من سجل KML.
    - لسجل KML بالارتباط بأكثر من سجل Excel.

    يحتفظ بأعلى مرشح حسب الدرجة ثم تشابه الاسم ثم المسافة.
    """
    accepted: list[MatchCandidate] = []
    rejected_conflicts: list[dict[str, Any]] = []

    used_excel_ids: set[str] = set()
    used_kml_ids: set[str] = set()

    for candidate in sorted(candidates, key=_candidate_sort_key):
        rejection_reason: str | None = None

        if candidate.excel_id in used_excel_ids:
            rejection_reason = "excel_record_already_matched"

        if candidate.kml_id in used_kml_ids:
            if rejection_reason:
                rejection_reason = (
                    "excel_and_kml_records_already_matched"
                )
            else:
                rejection_reason = "kml_record_already_matched"

        if rejection_reason:
            rejected_conflicts.append(
                {
                    **asdict(candidate),
                    "one_to_one_status": "rejected",
                    "one_to_one_reason": rejection_reason,
                }
            )
            continue

        used_excel_ids.add(candidate.excel_id)
        used_kml_ids.add(candidate.kml_id)
        accepted.append(candidate)

    return accepted, rejected_conflicts


def _record_lookup(
    records: list[SourceRecord],
) -> dict[str, SourceRecord]:
    return {
        record.source_id: record
        for record in records
    }


def _build_merge_preview(
    candidate: MatchCandidate,
    excel_record: SourceRecord,
    kml_record: SourceRecord,
) -> dict[str, Any]:
    """
    يبني معاينة الدمج دون تغيير المصادر أو قاعدة البيانات.
    """
    severity = _conflict_severity(candidate.conflict_fields)

    proposed_name_ar = (
        excel_record.name_ar
        or kml_record.name_ar
        or ""
    )

    proposed_name_en = (
        excel_record.name_en
        or kml_record.name_en
    )

    proposed_municipality = (
        excel_record.municipality
        or kml_record.municipality
    )

    proposed_category = (
        excel_record.category_code
        or kml_record.category_code
    )

    return {
        "excel_record_id": candidate.excel_id,
        "kml_record_id": candidate.kml_id,
        "match": {
            "confidence_score": candidate.confidence_score,
            "name_similarity": candidate.name_similarity,
            "distance_meters": candidate.distance_meters,
            "municipality_match": candidate.municipality_match,
            "category_match": candidate.category_match,
            "decision": candidate.decision,
        },
        "conflicts": {
            "items": candidate.conflict_fields,
            "severity": severity,
            "requires_manual_review": severity != "none",
        },
        "excel_source": {
            "source_id": excel_record.source_id,
            "name_ar": excel_record.name_ar,
            "name_en": excel_record.name_en,
            "municipality": excel_record.municipality,
            "category_code": excel_record.category_code,
            "latitude": excel_record.latitude,
            "longitude": excel_record.longitude,
            "description": excel_record.description,
            "source_reference": excel_record.source_reference,
            "properties": excel_record.properties,
        },
        "kml_source": {
            "source_id": kml_record.source_id,
            "name_ar": kml_record.name_ar,
            "name_en": kml_record.name_en,
            "municipality": kml_record.municipality,
            "category_code": kml_record.category_code,
            "latitude": kml_record.latitude,
            "longitude": kml_record.longitude,
            "description": kml_record.description,
            "source_reference": kml_record.source_reference,
            "properties": kml_record.properties,
        },
        "proposed_site": {
            "name_ar": proposed_name_ar,
            "name_en": proposed_name_en,
            "municipality": proposed_municipality,
            "category_code": proposed_category,
            "latitude": kml_record.latitude,
            "longitude": kml_record.longitude,
            "description": (
                excel_record.description
                or kml_record.description
            ),
        },
        "field_sources": {
            "geometry": "kml",
            "coordinates": "kml",
            "photos": "kml",
            "spatial_description": "kml",
            "name_ar": "excel_preferred",
            "name_en": "excel_preferred",
            "municipality": "excel_preferred",
            "category_code": "excel_preferred",
            "business_attributes": "excel",
            "operational_statistics": "excel",
        },
        "review": {
            "status": "pending_review",
            "decision": None,
            "reviewer_notes": "",
        },
    }


def _write_match_review_csv(
    candidates: list[MatchCandidate],
    output_path: Path,
) -> None:
    headers = [
        "excel_id",
        "kml_id",
        "excel_name",
        "kml_name",
        "name_similarity",
        "distance_meters",
        "municipality_match",
        "category_match",
        "confidence_score",
        "decision",
        "conflict_fields",
        "conflict_severity",
        "review_status",
        "reviewer_notes",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=headers,
        )
        writer.writeheader()

        for candidate in sorted(
            candidates,
            key=_candidate_sort_key,
        ):
            writer.writerow(
                {
                    "excel_id": candidate.excel_id,
                    "kml_id": candidate.kml_id,
                    "excel_name": candidate.excel_name,
                    "kml_name": candidate.kml_name,
                    "name_similarity": candidate.name_similarity,
                    "distance_meters": candidate.distance_meters,
                    "municipality_match": (
                        candidate.municipality_match
                    ),
                    "category_match": candidate.category_match,
                    "confidence_score": (
                        candidate.confidence_score
                    ),
                    "decision": candidate.decision,
                    "conflict_fields": "|".join(
                        candidate.conflict_fields
                    ),
                    "conflict_severity": _conflict_severity(
                        candidate.conflict_fields
                    ),
                    "review_status": "pending_review",
                    "reviewer_notes": "",
                }
            )


def _write_one_to_one_conflicts_csv(
    rejected_conflicts: list[dict[str, Any]],
    output_path: Path,
) -> None:
    headers = [
        "excel_id",
        "kml_id",
        "excel_name",
        "kml_name",
        "name_similarity",
        "distance_meters",
        "confidence_score",
        "decision",
        "conflict_fields",
        "one_to_one_status",
        "one_to_one_reason",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=headers,
            extrasaction="ignore",
        )
        writer.writeheader()

        for item in rejected_conflicts:
            conflict_fields = item.get("conflict_fields", [])

            writer.writerow(
                {
                    **item,
                    "conflict_fields": "|".join(conflict_fields),
                }
            )


def _write_unmatched_csv(
    records: list[SourceRecord],
    matched_ids: set[str],
    output_path: Path,
) -> None:
    headers = [
        "source_id",
        "source_type",
        "name_ar",
        "name_en",
        "municipality",
        "category_code",
        "latitude",
        "longitude",
        "source_reference",
        "review_status",
        "reviewer_notes",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=headers,
        )
        writer.writeheader()

        for record in records:
            if record.source_id in matched_ids:
                continue

            writer.writerow(
                {
                    "source_id": record.source_id,
                    "source_type": record.source_type,
                    "name_ar": record.name_ar,
                    "name_en": record.name_en,
                    "municipality": record.municipality,
                    "category_code": record.category_code,
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "source_reference": record.source_reference,
                    "review_status": "pending_review",
                    "reviewer_notes": "",
                }
            )


def run_match(
    excel_path: Path,
    geojson_path: Path,
    output_dir: Path,
    min_score: float = 65.0,
    max_distance: float = 1_000.0,
    layer_config: dict[str, Any] | None = None,
) -> dict[str, int | float | str]:
    """
    يشغل المطابقة بين Excel وKML/GeoJSON دون دمج فعلي.

    المخرجات:
    - CSV لمراجعة المطابقات المقبولة One-to-One.
    - JSON لمعاينة الدمج.
    - CSV لتعارضات One-to-One.
    - CSV لسجلات Excel غير المطابقة.
    - CSV لسجلات KML غير المطابقة.
    - JSON للملخص.
    """
    excel_path = Path(excel_path)
    geojson_path = Path(geojson_path)
    output_dir = Path(output_dir)

    if not excel_path.exists():
        raise FileNotFoundError(
            f"ملف Excel غير موجود: {excel_path}"
        )

    if not geojson_path.exists():
        raise FileNotFoundError(
            f"ملف GeoJSON غير موجود: {geojson_path}"
        )

    if min_score < 0 or min_score > 100:
        raise ValueError(
            "min_score يجب أن يكون بين 0 و100."
        )

    if max_distance <= 0:
        raise ValueError(
            "max_distance يجب أن يكون أكبر من صفر."
        )

    excel_rows = read_configured_excel(excel_path, layer_config) if layer_config else read_hotels_excel(excel_path)
    kml_rows = read_geojson(geojson_path)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_candidates = _build_all_candidates(
        excel_rows=excel_rows,
        kml_rows=kml_rows,
        min_score=min_score,
        max_distance=max_distance,
    )

    accepted_candidates, rejected_conflicts = (
        _enforce_one_to_one(all_candidates)
    )

    excel_lookup = _record_lookup(excel_rows)
    kml_lookup = _record_lookup(kml_rows)

    merge_previews: list[dict[str, Any]] = []

    for candidate in accepted_candidates:
        excel_record = excel_lookup.get(candidate.excel_id)
        kml_record = kml_lookup.get(candidate.kml_id)

        if excel_record is None or kml_record is None:
            continue

        merge_previews.append(
            _build_merge_preview(
                candidate=candidate,
                excel_record=excel_record,
                kml_record=kml_record,
            )
        )

    matched_excel_ids = {
        candidate.excel_id
        for candidate in accepted_candidates
    }

    matched_kml_ids = {
        candidate.kml_id
        for candidate in accepted_candidates
    }

    match_review_path = (
        output_dir
        / "hotels_kml_excel_match_review.csv"
    )

    conflict_path = (
        output_dir
        / "hotels_one_to_one_conflicts.csv"
    )

    preview_path = (
        output_dir
        / "hotels_merge_preview.json"
    )

    unmatched_excel_path = (
        output_dir
        / "hotels_unmatched_excel.csv"
    )

    unmatched_kml_path = (
        output_dir
        / "hotels_unmatched_kml.csv"
    )

    summary_path = (
        output_dir
        / "hotels_kml_excel_match_summary.json"
    )

    _write_match_review_csv(
        candidates=accepted_candidates,
        output_path=match_review_path,
    )

    _write_one_to_one_conflicts_csv(
        rejected_conflicts=rejected_conflicts,
        output_path=conflict_path,
    )

    _write_unmatched_csv(
        records=excel_rows,
        matched_ids=matched_excel_ids,
        output_path=unmatched_excel_path,
    )

    _write_unmatched_csv(
        records=kml_rows,
        matched_ids=matched_kml_ids,
        output_path=unmatched_kml_path,
    )

    preview_path.write_text(
        json.dumps(
            merge_previews,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    summary: dict[str, int | float | str] = {
        "status": "success_without_merge",
        "excel_records": len(excel_rows),
        "kml_records": len(kml_rows),
        "raw_candidate_pairs": len(all_candidates),
        "one_to_one_candidates": len(accepted_candidates),
        "one_to_one_rejected_conflicts": len(
            rejected_conflicts
        ),
        "ready_merge": sum(
            candidate.decision == "ready_merge"
            for candidate in accepted_candidates
        ),
        "needs_review": sum(
            candidate.decision == "needs_review"
            for candidate in accepted_candidates
        ),
        "possible_match": sum(
            candidate.decision == "possible_match"
            for candidate in accepted_candidates
        ),
        "high_conflict_candidates": sum(
            _conflict_severity(
                candidate.conflict_fields
            )
            == "high"
            for candidate in accepted_candidates
        ),
        "medium_conflict_candidates": sum(
            _conflict_severity(
                candidate.conflict_fields
            )
            == "medium"
            for candidate in accepted_candidates
        ),
        "no_conflict_candidates": sum(
            _conflict_severity(
                candidate.conflict_fields
            )
            == "none"
            for candidate in accepted_candidates
        ),
        "unmatched_excel_records": (
            len(excel_rows) - len(matched_excel_ids)
        ),
        "unmatched_kml_records": (
            len(kml_rows) - len(matched_kml_ids)
        ),
        "min_score": min_score,
        "max_distance_meters": max_distance,
        "database_writes": 0,
        "promotions": 0,
    }

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return summary
