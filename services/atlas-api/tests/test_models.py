from pathlib import Path

from app.db.base import Base
from app.models import ImportFeature, Site


def test_all_national_tables_are_registered() -> None:
    expected = {
        "atlas.site_categories",
        "atlas.municipalities",
        "atlas.data_sources",
        "atlas.sites",
        "atlas.site_geometries",
        "atlas.media_assets",
        "atlas.verification_records",
        "atlas.publication_records",
        "atlas.site_profiles",
        "atlas.site_attributes",
        "atlas.site_documents",
        "atlas.site_relationships",
        "atlas.site_quality_snapshots",
        "atlas.site_versions",
        "atlas.site_identifiers",
        "staging.import_batches",
        "staging.import_features",
        "staging.feature_reviews",
        "staging.promotion_records",
        "audit.audit_log",
    }
    assert expected.issubset(set(Base.metadata.tables))
    assert {name for name in Base.metadata.tables if name.startswith("metadata.")} == {
        "metadata.catalog_entries",
        "metadata.catalog_fields",
        "metadata.data_lineage_nodes",
        "metadata.data_lineage_edges",
        "metadata.data_quality_rules",
        "metadata.data_quality_results",
        "metadata.dataset_versions",
        "metadata.media_review_items",
    }


def test_models_use_expected_schemas_and_geometry() -> None:
    assert Site.__table__.schema == "atlas"
    assert ImportFeature.__table__.schema == "staging"
    assert ImportFeature.__table__.c.geometry.type.srid == 4326


def test_initial_migration_contains_every_table() -> None:
    migrations = list((Path(__file__).parents[1] / "alembic" / "versions").glob("*.py"))
    assert len(migrations) >= 6
    text = "\n".join(path.read_text(encoding="utf-8") for path in migrations)
    for table in Base.metadata.tables.values():
        assert table.name in text
    assert "geoalchemy2.types.Geometry" in text
