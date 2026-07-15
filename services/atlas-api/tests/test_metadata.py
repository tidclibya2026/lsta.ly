from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.services.data_lineage_service import create_lineage_edge, get_full_lineage_graph, get_or_create_node
from app.services.metadata_catalog_service import (
    calculate_catalog_completeness,
    create_catalog_entry,
    create_dataset_version,
    get_catalog_entry,
    list_catalog_entries,
    update_catalog_entry,
    upsert_catalog_field,
)
from app.services.metadata_quality_service import execute_rule, get_quality_summary, list_rules


@pytest.fixture
def metadata_session() -> Generator[Session, None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_seed_catalog_and_search(metadata_session: Session) -> None:
    items, total = list_catalog_entries(metadata_session, search="LSTA-API")
    assert total == 3
    assert all(item.entry_type == "api_endpoint" for item in items)


def test_catalog_create_update_field_version_and_completeness(metadata_session: Session) -> None:
    code = f"TEST-{uuid4()}"
    entry = create_catalog_entry(
        metadata_session,
        {"catalog_code": code, "entry_type": "dataset", "title_ar": "اختبار", "owning_organization": "LSTA"},
    )
    update_catalog_entry(metadata_session, code, {"description_ar": "وصف", "source_system": "pytest"})
    field = upsert_catalog_field(
        metadata_session, entry.id, "name_ar", {"label_ar": "الاسم", "data_type": "text", "required": True}
    )
    version = create_dataset_version(metadata_session, entry.id, {"row_count": 1})
    assert field.required and version.version_number == 1
    assert calculate_catalog_completeness(get_catalog_entry(metadata_session, code)) >= 70


def test_lineage_duplicate_and_cycle_prevention(metadata_session: Session) -> None:
    suffix = str(uuid4())
    source = get_or_create_node(metadata_session, "source_file", suffix, "source")
    target = get_or_create_node(metadata_session, "import_batch", suffix, "batch")
    first = create_lineage_edge(metadata_session, source, target, "imported_from", "pytest")
    assert create_lineage_edge(metadata_session, source, target, "imported_from", "pytest").id == first.id
    with pytest.raises(ValueError, match="circular"):
        create_lineage_edge(metadata_session, target, source, "replaced_by", "pytest")
    assert len(get_full_lineage_graph(metadata_session, source.id)["nodes"]) == 2


def test_quality_rule_execution_and_summary(metadata_session: Session) -> None:
    rule = next(item for item in list_rules(metadata_session) if item.rule_code == "SITE_NAME_AR_REQUIRED")
    result = execute_rule(metadata_session, rule, "atlas.sites", str(uuid4()), "")
    assert result.status == "failed"
    assert get_quality_summary(metadata_session)["failed"] >= 1
