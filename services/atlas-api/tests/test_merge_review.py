from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import create_database_engine
from app.main import app
from app.models import MergeBatch, MergeDecision, MergeProposal, PromotionRecord, Site
from app.services.merge_proposal_import_service import import_merge_proposals
from app.services.merge_review_service import bulk_decision_preview, get_merge_summary, submit_merge_decision

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def merge_session() -> Generator[Session, None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def _inputs() -> dict[str, Path]:
    return {"excel_path": ROOT / "data/raw/excel/أطلس_ليبيا_السياحي_2026_طبقة_الفنادق.xlsx", "kml_path": ROOT / "data/raw/kml/hotels_LY.kml", "summary_path": ROOT / "reports/merge/hotels/hotels_kml_excel_match_summary.json", "preview_path": ROOT / "reports/merge/hotels/hotels_merge_preview.json"}


def test_idempotent_import_and_no_registry_writes(merge_session: Session) -> None:
    merge_session.execute(delete(MergeDecision)); merge_session.execute(delete(MergeProposal)); merge_session.execute(delete(MergeBatch)); merge_session.flush()
    sites, promotions = merge_session.scalar(select(func.count()).select_from(Site)), merge_session.scalar(select(func.count()).select_from(PromotionRecord))
    first = import_merge_proposals(merge_session, **_inputs())
    second = import_merge_proposals(merge_session, **_inputs())
    assert (first["batch_created"], first["inserted"], first["invalid"]) == (True, 457, 0)
    assert (second["batch_created"], second["inserted"], second["duplicates"]) == (False, 0, 457)
    assert merge_session.scalar(select(func.count()).select_from(MergeDecision)) == 0
    assert merge_session.scalar(select(func.count()).select_from(Site)) == sites
    assert merge_session.scalar(select(func.count()).select_from(PromotionRecord)) == promotions


def test_summary_filters_pagination_and_bulk_preview(merge_session: Session) -> None:
    summary = get_merge_summary(merge_session)
    assert summary["proposals"] == 457 and summary["ready_merge"] == 433 and summary["high_conflicts"] == 9
    safe = list(merge_session.scalars(select(MergeProposal).where(MergeProposal.candidate_class == "ready_merge", MergeProposal.conflict_severity == "none").limit(2)))
    before = merge_session.scalar(select(func.count()).select_from(MergeDecision))
    preview = bulk_decision_preview(merge_session, [row.id for row in safe], "approved_merge")
    assert len(preview["eligible_ids"]) == 2 and preview["writes"] == 0
    assert merge_session.scalar(select(func.count()).select_from(MergeDecision)) == before


def test_high_conflict_rbac_and_history(merge_session: Session) -> None:
    high = merge_session.scalar(select(MergeProposal).where(MergeProposal.conflict_severity == "high"))
    assert high
    with pytest.raises(PermissionError):
        submit_merge_decision(merge_session, high, decision="approved_merge", role="reviewer")
    first = submit_merge_decision(merge_session, high, decision="needs_field_verification", role="gis_specialist")
    second = submit_merge_decision(merge_session, high, decision="approved_merge", role="data_manager")
    assert first.id != second.id and len(high.decisions) == 2


def test_api_visibility_and_missing_record(merge_session: Session) -> None:
    def override() -> Generator[Session, None, None]: yield merge_session
    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        assert client.get("/api/v1/merge-review/summary").status_code == 200
        assert client.get("/api/v1/merge-review/batches").status_code == 403
        headers = {"X-LSTA-Reviewer-Role": "reviewer"}
        batches = client.get("/api/v1/merge-review/batches", headers=headers).json()["items"]
        response = client.get(f"/api/v1/merge-review/batches/{batches[0]['id']}/proposals", params={"limit": 5, "candidate_class": "ready_merge"}, headers=headers)
        assert response.status_code == 200 and len(response.json()["items"]) == 5
        assert client.get("/api/v1/merge-review/proposals/00000000-0000-0000-0000-000000000000", headers=headers).status_code == 404
        assert "reviewer_reference" not in client.get(f"/api/v1/merge-review/proposals/{response.json()['items'][0]['id']}", headers=headers).text
    finally:
        app.dependency_overrides.clear()
