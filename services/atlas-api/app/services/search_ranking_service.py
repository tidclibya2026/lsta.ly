from __future__ import annotations

from typing import Any

from app.services.arabic_text_service import normalize_arabic_text


def calculate_ranking(document: dict[str, Any], query: str, *, development: bool = False) -> dict[str, Any]:
    q = normalize_arabic_text(query)
    ar = normalize_arabic_text(document.get("name_ar") or "")
    en = (document.get("name_en") or "").casefold()
    national_id = (document.get("national_id") or "").casefold()
    score, reason, matched = 0.0, "no text match", []
    if national_id and query.casefold() == national_id: score, reason, matched = 100, "exact national identifier", ["national_id"]
    elif q and q == ar: score, reason, matched = 95, "exact Arabic name", ["name_ar"]
    elif q and q == document.get("normalized_name_ar"): score, reason, matched = 92, "normalized Arabic name", ["normalized_name_ar"]
    elif en and query.casefold() == en: score, reason, matched = 90, "exact English name", ["name_en"]
    elif q and (ar.startswith(q) or en.startswith(query.casefold())): score, reason, matched = 85, "name prefix", ["name"]
    elif q and q in normalize_arabic_text(document.get("description_text") or ""): score, reason, matched = 55, "description", ["description_text"]
    breakdown = {"text": score}
    if document.get("source") == "registry" and document.get("verification_status") == "approved": score += 5; breakdown["approved_registry"] = 5
    if document.get("publication_status") == "approved_internal": score += 3; breakdown["approved_internal"] = 3
    score += min(3, float(document.get("completeness_score") or 0) * 0.03)
    score += min(3, float(document.get("quality_score") or 0) * 0.03)
    if document.get("has_images"): score += 2; breakdown["approved_image"] = 2
    if document.get("source") == "staging": score -= 5; breakdown["staging"] = -5
    if document.get("review_status") == "pending_review": score -= 3; breakdown["pending_review"] = -3
    result = {"relevance_score": round(max(0, min(100, score)), 2), "ranking_breakdown": breakdown, "matched_fields": matched}
    if development: result["ranking_reason"] = reason
    return result


def build_highlights(text: str | None, query: str) -> str | None:
    if not text or not query: return text
    return text.replace(query, f"<mark>{query}</mark>")
