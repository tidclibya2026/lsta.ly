"""Deterministic reference dataset for the isolated ``lsta_test`` database only."""
from __future__ import annotations

from pathlib import Path

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import Engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.db.session import session_factory
from app.models import (
    ImportFeature,
    MediaReviewItem,
    MergeProposal,
    PromotionRecord,
    Site,
    SiteGeometry,
    SiteProfile,
)
from app.services.import_old_tripoli_to_staging import import_old_tripoli
from app.services.media_review_import_service import import_review_csv
from app.services.merge_proposal_import_service import import_merge_proposals
from tests.merge_fixture import merge_input_paths

ROOT = Path(__file__).resolve().parents[3]

# Static metadata and quality-rule rows inserted by migrations are deliberately retained.
RESET_TABLES = (
    "audit.merge_execution_events",
    "audit.audit_log",
    "atlas.site_relationships",
    "atlas.site_documents",
    "atlas.site_attributes",
    "atlas.site_quality_snapshots",
    "atlas.site_versions",
    "atlas.site_profiles",
    "atlas.media_assets",
    "atlas.site_geometries",
    "atlas.verification_records",
    "atlas.publication_records",
    "staging.merge_execution_items",
    "staging.merge_execution_batches",
    "staging.merge_decisions",
    "staging.merge_proposals",
    "staging.merge_batches",
    "staging.feature_reviews",
    "staging.promotion_records",
    "staging.import_features",
    "staging.import_batches",
    "metadata.media_review_items",
    "search.search_logs",
    "atlas.sites",
    "atlas.data_sources",
)


def _guard(database_url: str) -> None:
    if make_url(database_url).database != "lsta_test":
        raise RuntimeError("Test seed is restricted to the lsta_test database")


def _reset(engine: Engine) -> None:
    with engine.begin() as connection:
        existing = {
            f"{schema}.{table}"
            for schema, table in connection.execute(
                text(
                    "SELECT schemaname, tablename FROM pg_tables "
                    "WHERE schemaname IN ('atlas','staging','audit','metadata','search')"
                )
            )
        }
        tables = [table for table in RESET_TABLES if table in existing]
        if tables:
            connection.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))


def _seed_sources(engine: Engine) -> None:
    factory = session_factory(engine)
    import_old_tripoli(
        ROOT / "data/processed/kml/old_tripoli.geojson",
        ROOT / "data/processed/kml/old_tripoli_manifest.json",
        factory,
    )
    with factory.begin() as session:
        import_review_csv(session, ROOT / "reports/media/old_tripoli_image_review.csv")
    with factory() as session:
        import_merge_proposals(session, **merge_input_paths())


def _seed_registry(engine: Engine) -> None:
    with Session(engine) as session:
        feature = session.scalar(
            select(ImportFeature)
            .where(ImportFeature.geometry_type == "Point", ImportFeature.missing_name.is_(False))
            .order_by(ImportFeature.source_feature_id)
        )
        if feature is None:
            raise RuntimeError("Reference staging dataset has no named Point feature")
        site = Site(
            national_id="LSTA-OLD-TRIPOLI-000001",
            name_ar="المدينة القديمة طرابلس",
            description="موقع مرجعي لاختبارات منصة أطلس ليبيا السياحي الذكي",
            verification_status="approved",
            profile_completeness_score=100,
        )
        session.add(site)
        session.flush()
        geometry = SiteGeometry(
            site_id=site.id,
            geometry_type="Point",
            geometry=from_shape(Point(13.1807868, 32.8958861), srid=4326),
        )
        session.add_all(
            [
                geometry,
                SiteProfile(
                    site_id=site.id,
                    short_description_ar="موقع اختباري مرجعي",
                    visitor_information={},
                    accessibility_information={},
                    opening_hours={},
                    contact_information={},
                ),
                PromotionRecord(
                    import_feature_id=feature.id,
                    site_id=site.id,
                    status="promoted",
                    snapshot={"test_seed": True},
                ),
            ]
        )
        session.flush()
        site.primary_geometry_id = geometry.id
        session.execute(text("SELECT setval('atlas.old_tripoli_national_id_seq', 1, true)"))
        session.commit()


def _validate(engine: Engine) -> None:
    with Session(engine) as session:
        expected = {
            "staging": (ImportFeature, 430),
            "media": (MediaReviewItem, 380),
            "proposals": (MergeProposal, 457),
        }
        for label, (model, count) in expected.items():
            actual = int(session.scalar(select(func.count()).select_from(model)) or 0)
            if actual != count:
                raise RuntimeError(f"Invalid {label} test seed: expected {count}, got {actual}")
        distribution = dict(
            session.execute(
                select(ImportFeature.geometry_type, func.count()).group_by(ImportFeature.geometry_type)
            ).all()
        )
        if distribution != {"LineString": 285, "Point": 135, "Polygon": 10}:
            raise RuntimeError(f"Invalid geometry distribution in test seed: {distribution}")


def reset_and_seed_test_database(engine: Engine, database_url: str) -> None:
    _guard(database_url)
    _reset(engine)
    _seed_sources(engine)
    _seed_registry(engine)
    _validate(engine)
