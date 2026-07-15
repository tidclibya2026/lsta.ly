from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QueryStatistic, SavedQuery, SearchLog, SearchSuggestion
from app.services.arabic_text_service import normalize_arabic_text
from app.services.search_service import autocomplete as legacy_autocomplete
from app.services.search_service import faceted_search, unified_search


def search(session: Session, query: str, *, role: str, source: str = "all", log: bool = True, **filters: Any) -> dict[str, Any]:
    started = time.perf_counter()
    result = unified_search(session, query, source=source, **filters)
    result["query_time_ms"] = round((time.perf_counter() - started) * 1000, 3)
    result["total_count"] = result.pop("total", len(result.get("items", [])))
    result["has_more"] = result.get("offset", 0) + len(result.get("items", [])) < result["total_count"]
    result["applied_filters"] = {key: value for key, value in {"source": source, **filters}.items() if value is not None}
    if log: log_search(session, query, role, source, result["total_count"], result["query_time_ms"], result["applied_filters"])
    return result


def search_registry(session: Session, query: str, **kw: Any): return search(session, query, role=kw.pop("role", "viewer"), source="registry", **kw)
def search_staging(session: Session, query: str, **kw: Any): return search(session, query, role=kw.pop("role", "reviewer"), source="staging", **kw)
def search_metadata(session: Session, query: str, **kw: Any): return {"items": [], "total_count": 0, "query_time_ms": 0.0, "source": "metadata"}
def search_media(session: Session, query: str, **kw: Any): return {"items": [], "total_count": 0, "query_time_ms": 0.0, "source": "media"}
def spatial_search(session: Session, query: str = "", **kw: Any): return search(session, query, **kw)
def faceted_search_results(session: Session): return faceted_search(session)
def autocomplete(session: Session, query: str, *, source: str = "all", limit: int = 10): return legacy_autocomplete(session, query, source=source, limit=min(limit, 10))
def suggest(session: Session, query: str, limit: int = 10):
    normalized = normalize_arabic_text(query)
    return list(session.scalars(select(SearchSuggestion).where(SearchSuggestion.is_active.is_(True), SearchSuggestion.normalized_text.ilike(f"{normalized}%")).order_by(SearchSuggestion.popularity_score.desc()).limit(limit)))


def log_search(session: Session, query: str, role: str, source: str, result_count: int, query_time_ms: float, filters: dict[str, Any]) -> SearchLog:
    normalized = normalize_arabic_text(query)
    row = SearchLog(role=role, query_text=query, normalized_query=normalized, source_scope=source, filters=filters, result_count=result_count, query_time_ms=query_time_ms, no_results=result_count == 0)
    session.add(row); update_query_statistics(session, normalized, result_count, query_time_ms); session.flush(); return row


def update_query_statistics(session: Session, normalized_query: str, count: int, milliseconds: float) -> QueryStatistic:
    stat = session.scalar(select(QueryStatistic).where(QueryStatistic.normalized_query == normalized_query))
    if not stat: stat = QueryStatistic(normalized_query=normalized_query); session.add(stat)
    old = stat.total_searches or 0; stat.total_searches = old + 1; stat.successful_searches = (stat.successful_searches or 0) + (count > 0); stat.no_result_searches = (stat.no_result_searches or 0) + (count == 0); stat.average_result_count = ((float(stat.average_result_count or 0) * old) + count) / (old + 1); stat.average_query_time_ms = ((float(stat.average_query_time_ms or 0) * old) + milliseconds) / (old + 1); stat.last_searched_at = datetime.now(timezone.utc); return stat


def save_query(session: Session, payload: dict[str, Any]) -> SavedQuery:
    row = SavedQuery(query_name=payload["query_name"], query_text=payload.get("query_text", ""), normalized_query=normalize_arabic_text(payload.get("query_text", "")), filters=payload.get("filters", {}), spatial_filter=payload.get("spatial_filter"), sort_by=payload.get("sort_by"), sort_order=payload.get("sort_order"), is_shared=payload.get("is_shared", False)); session.add(row); session.flush(); return row
def list_saved_queries(session: Session): return list(session.scalars(select(SavedQuery).where(SavedQuery.is_active.is_(True)).order_by(SavedQuery.updated_at.desc())))
def get_saved_query(session: Session, query_id: UUID): return session.get(SavedQuery, query_id)
def delete_saved_query(session: Session, query_id: UUID) -> bool:
    row = session.get(SavedQuery, query_id)
    if not row: return False
    row.is_active = False; return True
def rerun_saved_query(session: Session, row: SavedQuery, role: str): return search(session, row.query_text, role=role, **row.filters)
def calculate_ranking(*args, **kwargs):
    from app.services.search_ranking_service import calculate_ranking as rank
    return rank(*args, **kwargs)
def build_highlights(*args, **kwargs):
    from app.services.search_ranking_service import build_highlights
    return build_highlights(*args, **kwargs)
def calculate_query_time(started: float) -> float: return round((time.perf_counter() - started) * 1000, 3)
