from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import DataSource, ImportFeature, Site
from app.services.import_old_tripoli_to_staging import (
    DuplicateSourceError,
    build_staging_features,
    complete_batch_transaction,
    guard_duplicate,
)

ROOT = Path(__file__).parents[3]
GEOJSON = ROOT / "data" / "processed" / "kml" / "old_tripoli.geojson"


@pytest.fixture(scope="module")
def records() -> list[ImportFeature]:
    features = json.loads(GEOJSON.read_text(encoding="utf-8"))["features"]
    return build_staging_features(features, uuid.uuid4())


def test_import_builds_430_staging_records(records: list[ImportFeature]) -> None:
    assert len(records) == 430


@pytest.mark.parametrize(("kind", "count"), [("Point", 135), ("LineString", 285), ("Polygon", 10)])
def test_geometry_distribution(records: list[ImportFeature], kind: str, count: int) -> None:
    assert sum(record.geometry_type == kind for record in records) == count


def test_missing_name_is_preserved(records: list[ImportFeature]) -> None:
    assert sum(record.missing_name for record in records) == 236
    assert all(record.review_status == "pending_review" for record in records)


def test_duplicate_sha_is_rejected() -> None:
    source = DataSource(name="x", source_file="x.geojson", source_type="geojson", sha256="a" * 64, manifest={})
    with pytest.raises(DuplicateSourceError):
        guard_duplicate(source, force=False)
    guard_duplicate(source, force=True)


def test_transaction_context_rolls_back_on_insert_error() -> None:
    factory = MagicMock()
    transaction = factory.begin.return_value
    session = transaction.__enter__.return_value
    session.add_all.side_effect = RuntimeError("forced failure")
    with pytest.raises(RuntimeError, match="forced failure"):
        complete_batch_transaction(factory, uuid.uuid4(), [], "a" * 64)
    transaction.__exit__.assert_called_once()


def test_staging_builder_never_creates_atlas_sites(records: list[ImportFeature]) -> None:
    assert all(isinstance(record, ImportFeature) for record in records)
    assert not any(isinstance(record, Site) for record in records)
