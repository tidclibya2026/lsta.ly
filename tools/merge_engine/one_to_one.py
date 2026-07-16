from __future__ import annotations

from collections import defaultdict

from tools.merge_engine.models import MatchCandidate


def enforce_one_to_one(
    candidates: list[MatchCandidate],
) -> list[MatchCandidate]:
    """
    يحتفظ بأفضل تطابق لكل سجل Excel ولكل سجل KML.

    لا ينفذ أي دمج، بل يحدد المرشحين المتعارضين
    ويرتبهم حسب أعلى درجة ثم أقصر مسافة.
    """
    sorted_candidates = sorted(
        candidates,
        key=lambda item: (
            -item.total_score,
            item.distance_meters
            if item.distance_meters is not None
            else float("inf"),
        ),
    )

    used_excel_ids: set[str] = set()
    used_kml_ids: set[str] = set()
    accepted: list[MatchCandidate] = []

    for candidate in sorted_candidates:
        if candidate.excel_record_id in used_excel_ids:
            candidate.decision = "conflict_excel_already_matched"
            continue

        if candidate.kml_record_id in used_kml_ids:
            candidate.decision = "conflict_kml_already_matched"
            continue

        used_excel_ids.add(candidate.excel_record_id)
        used_kml_ids.add(candidate.kml_record_id)
        accepted.append(candidate)

    return accepted


def find_duplicate_assignments(
    candidates: list[MatchCandidate],
) -> dict[str, list[MatchCandidate]]:
    grouped: dict[str, list[MatchCandidate]] = defaultdict(list)

    for candidate in candidates:
        grouped[candidate.kml_record_id].append(candidate)

    return {
        kml_id: group
        for kml_id, group in grouped.items()
        if len(group) > 1
    }