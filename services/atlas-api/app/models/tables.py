from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

VERIFICATION_STATUSES = (
    "draft",
    "imported",
    "pending_review",
    "needs_correction",
    "gis_review",
    "data_review",
    "approved",
    "rejected",
    "archived",
)
PUBLICATION_STATUSES = (
    "internal",
    "approved_internal",
    "approved_public",
    "published_public",
    "sent_to_visit_libya",
    "withdrawn",
)
REVIEW_STATUSES = ("pending_review", "accepted", "rejected", "needs_correction")
REVIEW_STAGES = ("technical", "gis", "data", "final")
REVIEW_DECISIONS = ("pending", "accepted", "rejected", "needs_correction")
PROMOTION_STATUSES = ("pending", "promoted", "failed", "cancelled")
DUPLICATE_STATUSES = ("pending_review", "confirmed_duplicate", "not_duplicate", "merged", "ignored")
SEARCH_INDEX_STATUSES = ("pending", "indexed", "failed", "stale")


def status_check(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name)


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class SiteCategory(UUIDPrimaryKey, Base):
    __tablename__ = "site_categories"
    __table_args__ = {"schema": "atlas"}
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))


class Municipality(UUIDPrimaryKey, Base):
    __tablename__ = "municipalities"
    __table_args__ = {"schema": "atlas"}
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255))


class DataSource(UUIDPrimaryKey, Base):
    __tablename__ = "data_sources"
    __table_args__ = (UniqueConstraint("sha256", name="uq_data_sources_sha256"), {"schema": "atlas"})
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_file: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="geojson")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Site(UUIDPrimaryKey, Base):
    __tablename__ = "sites"
    __table_args__ = (
        status_check("verification_status", VERIFICATION_STATUSES, "sites_verification_status"),
        Index("ix_sites_name_ar_trgm", "name_ar", postgresql_using="gin", postgresql_ops={"name_ar": "gin_trgm_ops"}),
        Index("ix_sites_name_en_trgm", "name_en", postgresql_using="gin", postgresql_ops={"name_en": "gin_trgm_ops"}),
        Index("ix_sites_search_vector_gin", "search_vector", postgresql_using="gin"),
        {"schema": "atlas"},
    )
    national_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.site_categories.id"))
    municipality_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.municipalities.id"))
    data_source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.data_sources.id"))
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    slug: Mapped[str | None] = mapped_column(String(600), unique=True)
    profile_completeness_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    primary_geometry_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    primary_media_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    normalized_name_ar: Mapped[str | None] = mapped_column(Text)
    normalized_name_en: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)


class SiteGeometry(UUIDPrimaryKey, Base):
    __tablename__ = "site_geometries"
    __table_args__ = (
        Index("ix_site_geometries_geometry_gist", "geometry", postgresql_using="gist"),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    geometry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    geometry: Mapped[Any] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False)


class MediaAsset(UUIDPrimaryKey, Base):
    __tablename__ = "media_assets"
    __table_args__ = {"schema": "atlas"}
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(50), nullable=False, default="image")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    caption_ar: Mapped[str | None] = mapped_column(Text)
    caption_en: Mapped[str | None] = mapped_column(Text)
    alt_text_ar: Mapped[str | None] = mapped_column(Text)
    alt_text_en: Mapped[str | None] = mapped_column(Text)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    publication_status: Mapped[str] = mapped_column(String(40), nullable=False, default="internal", index=True)


class SiteProfile(UUIDPrimaryKey, Base):
    __tablename__ = "site_profiles"
    __table_args__ = ({"schema": "atlas"},)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    short_description_ar: Mapped[str | None] = mapped_column(Text)
    short_description_en: Mapped[str | None] = mapped_column(Text)
    historical_period: Mapped[str | None] = mapped_column(Text)
    tourism_significance: Mapped[str | None] = mapped_column(Text)
    visitor_information: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    accessibility_information: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    opening_hours: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    contact_information: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    official_website: Mapped[str | None] = mapped_column(Text)
    public_notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SiteAttribute(UUIDPrimaryKey, Base):
    __tablename__ = "site_attributes"
    __table_args__ = (
        UniqueConstraint("site_id", "attribute_group", "attribute_key", name="uq_site_attribute_key"),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attribute_group: Mapped[str] = mapped_column(String(120), nullable=False)
    attribute_key: Mapped[str] = mapped_column(String(160), nullable=False)
    label_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(255))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[float | None] = mapped_column(Numeric)
    value_boolean: Mapped[bool | None] = mapped_column(Boolean)
    value_date: Mapped[date | None] = mapped_column()
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(80))
    source_reference: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SiteDocument(UUIDPrimaryKey, Base):
    __tablename__ = "site_documents"
    __table_args__ = (
        Index(
            "ix_site_documents_title_ar_trgm",
            "title_ar",
            postgresql_using="gin",
            postgresql_ops={"title_ar": "gin_trgm_ops"},
        ),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(Text)
    original_url: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(150))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    document_date: Mapped[date | None] = mapped_column()
    issuing_organization: Mapped[str | None] = mapped_column(String(500))
    rights_status: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    publication_status: Mapped[str] = mapped_column(String(40), nullable=False, default="internal", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SiteRelationship(UUIDPrimaryKey, Base):
    __tablename__ = "site_relationships"
    __table_args__ = (
        CheckConstraint(
            "(target_site_id IS NOT NULL) <> (target_staging_feature_id IS NOT NULL)",
            name="site_relationship_one_target",
        ),
        CheckConstraint(
            "target_site_id IS NULL OR source_site_id <> target_site_id", name="site_relationship_not_self"
        ),
        Index(
            "uq_site_relationship_registry",
            "source_site_id",
            "target_site_id",
            "relationship_type",
            unique=True,
            postgresql_where=text("target_site_id IS NOT NULL"),
        ),
        Index(
            "uq_site_relationship_staging",
            "source_site_id",
            "target_staging_feature_id",
            "relationship_type",
            unique=True,
            postgresql_where=text("target_staging_feature_id IS NOT NULL"),
        ),
        Index("ix_site_relationships_metadata_gin", "relationship_metadata", postgresql_using="gin"),
        {"schema": "atlas"},
    )
    source_site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_site_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), index=True
    )
    target_staging_feature_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("staging.import_features.id", ondelete="CASCADE"), index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    relationship_direction: Mapped[str] = mapped_column(
        String(30), nullable=False, default="outbound", server_default="outbound"
    )
    distance_meters: Mapped[float | None] = mapped_column(Numeric)
    travel_time_minutes: Mapped[float | None] = mapped_column(Numeric)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    relationship_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_method: Mapped[str] = mapped_column(String(40), nullable=False, default="manual", server_default="manual")
    verification_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="pending_review", server_default="pending_review", index=True
    )
    publication_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="internal", server_default="internal", index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SiteQualitySnapshot(UUIDPrimaryKey, Base):
    __tablename__ = "site_quality_snapshots"
    __table_args__ = ({"schema": "atlas"},)
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    critical_issues: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    calculated_by: Mapped[str] = mapped_column(String(120), nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(80))


class SiteVersion(UUIDPrimaryKey, Base):
    __tablename__ = "site_versions"
    __table_args__ = (UniqueConstraint("site_id", "version_number", name="uq_site_version"), {"schema": "atlas"})
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SiteIdentifier(UUIDPrimaryKey, Base):
    __tablename__ = "site_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_type", "identifier_value", name="uq_site_identifier_value"),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    identifier_type: Mapped[str] = mapped_column(String(100), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    issuing_authority: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class VerificationRecord(UUIDPrimaryKey, Base):
    __tablename__ = "verification_records"
    __table_args__ = (
        status_check("verification_status", VERIFICATION_STATUSES, "verification_records_status"),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublicationRecord(UUIDPrimaryKey, Base):
    __tablename__ = "publication_records"
    __table_args__ = (
        status_check("publication_status", PUBLICATION_STATUSES, "publication_records_status"),
        {"schema": "atlas"},
    )
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    publication_status: Mapped[str] = mapped_column(String(40), nullable=False, default="internal", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class ImportBatch(UUIDPrimaryKey, Base):
    __tablename__ = "import_batches"
    __table_args__ = {"schema": "staging"}
    data_source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.data_sources.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running")
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    features: Mapped[list[ImportFeature]] = relationship(back_populates="batch", cascade="all, delete-orphan")


class ImportFeature(UUIDPrimaryKey, Base):
    __tablename__ = "import_features"
    __table_args__ = (
        status_check("review_status", REVIEW_STATUSES, "import_features_review_status"),
        Index("ix_import_features_geometry_gist", "geometry", postgresql_using="gist"),
        Index("ix_import_features_batch_id", "batch_id"),
        Index("ix_import_features_source_feature_id", "source_feature_id"),
        Index(
            "ix_import_features_name_ar_trgm",
            "name_ar",
            postgresql_using="gin",
            postgresql_ops={"name_ar": "gin_trgm_ops"},
        ),
        Index("ix_import_features_search_vector_gin", "search_vector", postgresql_using="gin"),
        {"schema": "staging"},
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staging.import_batches.id", ondelete="CASCADE"), nullable=False
    )
    source_feature_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str | None] = mapped_column(String(500))
    geometry_type: Mapped[str] = mapped_column(String(40), nullable=False)
    geometry: Mapped[Any] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_issues: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    missing_name: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_review")
    proposed_national_id: Mapped[str | None] = mapped_column(String(100))
    proposed_category_code: Mapped[str | None] = mapped_column(String(80))
    proposed_municipality_code: Mapped[str | None] = mapped_column(String(80))
    promotion_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    normalized_name_ar: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR)
    batch: Mapped[ImportBatch] = relationship(back_populates="features")


class FeatureReview(UUIDPrimaryKey, Base):
    __tablename__ = "feature_reviews"
    __table_args__ = (
        status_check("review_stage", REVIEW_STAGES, "feature_reviews_stage"),
        status_check("decision", REVIEW_DECISIONS, "feature_reviews_decision"),
        UniqueConstraint("import_feature_id", "review_stage", name="uq_feature_reviews_feature_stage"),
        {"schema": "staging"},
    )
    import_feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staging.import_features.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewer_role: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    proposed_name_ar: Mapped[str | None] = mapped_column(String(500))
    proposed_category_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.site_categories.id"))
    proposed_municipality_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.municipalities.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PromotionRecord(UUIDPrimaryKey, Base):
    __tablename__ = "promotion_records"
    __table_args__ = (
        status_check("status", PROMOTION_STATUSES, "promotion_records_status"),
        UniqueConstraint("import_feature_id", name="uq_promotion_records_import_feature"),
        {"schema": "staging"},
    )
    import_feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("staging.import_features.id", ondelete="CASCADE"), nullable=False
    )
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.sites.id"))
    promoted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class AuditLog(UUIDPrimaryKey, Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "audit"}
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CatalogEntry(UUIDPrimaryKey, Base):
    __tablename__ = "catalog_entries"
    __table_args__ = ({"schema": "metadata"},)
    catalog_code: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(40), index=True)
    title_ar: Mapped[str] = mapped_column(String(500))
    title_en: Mapped[str | None] = mapped_column(String(500))
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    owning_organization: Mapped[str] = mapped_column(String(500))
    steward_name: Mapped[str | None] = mapped_column(String(300))
    technical_owner: Mapped[str | None] = mapped_column(String(300))
    source_system: Mapped[str | None] = mapped_column(String(300))
    source_reference: Mapped[str | None] = mapped_column(Text)
    classification_level: Mapped[str] = mapped_column(String(30), default="internal")
    sensitivity_level: Mapped[str] = mapped_column(String(20), default="low")
    lifecycle_status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    verification_status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    publication_status: Mapped[str] = mapped_column(String(40), default="internal", index=True)
    metadata_standard: Mapped[str] = mapped_column(String(100), default="LSTA")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CatalogField(UUIDPrimaryKey, Base):
    __tablename__ = "catalog_fields"
    __table_args__ = (UniqueConstraint("catalog_entry_id", "field_name"), {"schema": "metadata"})
    catalog_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("metadata.catalog_entries.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(200))
    label_ar: Mapped[str] = mapped_column(String(300))
    label_en: Mapped[str | None] = mapped_column(String(300))
    data_type: Mapped[str] = mapped_column(String(100))
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_identifier: Mapped[bool] = mapped_column(Boolean, default=False)
    is_spatial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    allowed_values: Mapped[Any | None] = mapped_column(JSONB)
    unit: Mapped[str | None] = mapped_column(String(100))
    source_field: Mapped[str | None] = mapped_column(String(200))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataLineageNode(UUIDPrimaryKey, Base):
    __tablename__ = "data_lineage_nodes"
    __table_args__ = (UniqueConstraint("node_type", "node_reference"), {"schema": "metadata"})
    node_type: Mapped[str] = mapped_column(String(40), index=True)
    node_reference: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(500))
    system_name: Mapped[str] = mapped_column(String(200))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataLineageEdge(UUIDPrimaryKey, Base):
    __tablename__ = "data_lineage_edges"
    __table_args__ = (
        UniqueConstraint("source_node_id", "target_node_id", "transformation_type"),
        {"schema": "metadata"},
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata.data_lineage_nodes.id"), index=True)
    target_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata.data_lineage_nodes.id"), index=True)
    transformation_type: Mapped[str] = mapped_column(String(40), index=True)
    transformation_reference: Mapped[str | None] = mapped_column(Text)
    process_name: Mapped[str] = mapped_column(String(300))
    process_version: Mapped[str | None] = mapped_column(String(80))
    executed_by: Mapped[str | None] = mapped_column(String(200))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(20), default="success")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityRule(UUIDPrimaryKey, Base):
    __tablename__ = "data_quality_rules"
    __table_args__ = ({"schema": "metadata"},)
    rule_code: Mapped[str] = mapped_column(String(160), unique=True)
    name_ar: Mapped[str] = mapped_column(String(500))
    name_en: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    target_entity: Mapped[str] = mapped_column(String(160), index=True)
    target_field: Mapped[str | None] = mapped_column(String(160))
    rule_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(20), index=True)
    rule_expression: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataQualityResult(UUIDPrimaryKey, Base):
    __tablename__ = "data_quality_results"
    __table_args__ = ({"schema": "metadata"},)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata.data_quality_rules.id"))
    entity_type: Mapped[str] = mapped_column(String(160))
    entity_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    issue_details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    evaluated_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetVersion(UUIDPrimaryKey, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("catalog_entry_id", "version_number"), {"schema": "metadata"})
    catalog_entry_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata.catalog_entries.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    version_label: Mapped[str] = mapped_column(String(160))
    checksum: Mapped[str | None] = mapped_column(String(64))
    schema_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    spatial_feature_count: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    release_notes: Mapped[str | None] = mapped_column(Text)


class MediaReviewItem(UUIDPrimaryKey, Base):
    __tablename__ = "media_review_items"
    __table_args__ = (
        UniqueConstraint("feature_id", "original_url", name="uq_media_review_feature_url"),
        Index("ix_media_review_status", "review_status"),
        Index("ix_media_review_rights", "rights_status"),
        Index("ix_media_review_download", "download_status"),
        Index("ix_media_review_domain", "domain"),
        {"schema": "metadata"},
    )
    feature_id: Mapped[str] = mapped_column(String(255), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.sites.id"))
    site_name: Mapped[str | None] = mapped_column(String(500))
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    rights_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    rights_owner: Mapped[str | None] = mapped_column(String(500))
    rights_evidence: Mapped[str | None] = mapped_column(Text)
    intended_use: Mapped[str] = mapped_column(String(40), nullable=False, default="internal_review")
    reviewer_role: Mapped[str | None] = mapped_column(String(100))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_requested")
    local_media_url: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SavedQuery(UUIDPrimaryKey, Base):
    __tablename__ = "saved_queries"
    __table_args__ = (Index("ix_saved_queries_normalized_query", "normalized_query"), Index("ix_saved_queries_filters_gin", "filters", postgresql_using="gin"), Index("ix_saved_queries_spatial_filter_gin", "spatial_filter", postgresql_using="gin"), {"schema": "search"})
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    query_name: Mapped[str] = mapped_column(String(300), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    spatial_filter: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sort_by: Mapped[str | None] = mapped_column(String(60))
    sort_order: Mapped[str | None] = mapped_column(String(10))
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SearchLog(UUIDPrimaryKey, Base):
    __tablename__ = "search_logs"
    __table_args__ = (Index("ix_search_logs_created_at", "created_at"), Index("ix_search_logs_no_results", "no_results"), Index("ix_search_logs_role", "role"), {"schema": "search"})
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    role: Mapped[str | None] = mapped_column(String(80))
    query_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_scope: Mapped[str] = mapped_column(String(40), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    query_time_ms: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    selected_result_type: Mapped[str | None] = mapped_column(String(80))
    selected_result_id: Mapped[str | None] = mapped_column(Text)
    no_results: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class QueryStatistic(UUIDPrimaryKey, Base):
    __tablename__ = "query_statistics"
    __table_args__ = ({"schema": "search"},)
    normalized_query: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    total_searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    no_result_searches: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_result_count: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    average_query_time_ms: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    last_searched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SearchSuggestion(UUIDPrimaryKey, Base):
    __tablename__ = "search_suggestions"
    __table_args__ = (UniqueConstraint("normalized_text", "suggestion_type", "source_reference"), Index("ix_search_suggestions_popularity", "popularity_score"), Index("ix_search_suggestions_relevance", "relevance_score"), {"schema": "search"})
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_reference: Mapped[str | None] = mapped_column(Text)
    popularity_score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    relevance_score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DuplicateCandidate(UUIDPrimaryKey, Base):
    __tablename__ = "duplicate_candidates"
    __table_args__ = (UniqueConstraint("source_entity_type", "source_entity_id", "target_entity_type", "target_entity_id"), status_check("status", DUPLICATE_STATUSES, "duplicate_candidate_status"), Index("ix_duplicate_confidence", "confidence_score"), Index("ix_duplicate_status", "status"), {"schema": "search"})
    source_entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    name_similarity: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    spatial_distance_meters: Mapped[float | None] = mapped_column(Numeric)
    description_similarity: Mapped[float | None] = mapped_column(Numeric(5, 2))
    category_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    municipality_match: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SimilarSiteCache(UUIDPrimaryKey, Base):
    __tablename__ = "similar_site_cache"
    __table_args__ = (UniqueConstraint("source_site_id", "target_site_id", "calculation_version"), Index("ix_similar_source", "source_site_id"), Index("ix_similar_target", "target_site_id"), {"schema": "search"})
    source_site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    target_site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atlas.sites.id", ondelete="CASCADE"), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    similarity_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(40), nullable=False)


class SearchIndexStatus(UUIDPrimaryKey, Base):
    __tablename__ = "search_index_status"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "index_version"), status_check("status", SEARCH_INDEX_STATUSES, "search_index_status_value"), {"schema": "search"})
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    index_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DashboardSnapshot(UUIDPrimaryKey, Base):
    __tablename__ = "dashboard_snapshots"
    __table_args__ = (UniqueConstraint("snapshot_date", "snapshot_type"), Index("ix_dashboard_snapshot_date", "snapshot_date"), Index("ix_dashboard_metrics_gin", "metrics", postgresql_using="gin"), {"schema": "executive"})
    snapshot_date: Mapped[date] = mapped_column(nullable=False)
    snapshot_type: Mapped[str] = mapped_column(String(20), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    generated_by: Mapped[str | None] = mapped_column(String(120))
    source_version: Mapped[str | None] = mapped_column(String(100))


class ExecutiveAlert(UUIDPrimaryKey, Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_executive_alert_status", "status"), Index("ix_executive_alert_severity", "severity"), Index("ix_executive_alert_type", "alert_type"), {"schema": "executive"})
    alert_code: Mapped[str] = mapped_column(String(120), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    title_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(500))
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text)
    source_entity_type: Mapped[str | None] = mapped_column(String(80))
    source_entity_id: Mapped[str | None] = mapped_column(Text)
    metric_name: Mapped[str | None] = mapped_column(String(120))
    metric_value: Mapped[float | None] = mapped_column(Numeric)
    threshold_value: Mapped[float | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    assigned_role: Mapped[str | None] = mapped_column(String(80))
    acknowledged_by: Mapped[str | None] = mapped_column(String(120))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(120))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KpiDefinition(UUIDPrimaryKey, Base):
    __tablename__ = "kpi_definitions"
    __table_args__ = (Index("ix_kpi_code", "kpi_code"), {"schema": "executive"})
    kpi_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(500), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(500))
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    calculation_method: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    target_value: Mapped[float | None] = mapped_column(Numeric)
    warning_threshold: Mapped[float | None] = mapped_column(Numeric)
    critical_threshold: Mapped[float | None] = mapped_column(Numeric)
    direction: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KpiValue(UUIDPrimaryKey, Base):
    __tablename__ = "kpi_values"
    __table_args__ = (Index("ix_kpi_measured_at", "measured_at"), Index("ix_kpi_evaluation", "evaluation_status"), Index("ix_kpi_dimensions_gin", "dimensions", postgresql_using="gin"), {"schema": "executive"})
    kpi_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("executive.kpi_definitions.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Numeric)
    change_value: Mapped[float | None] = mapped_column(Numeric)
    change_percentage: Mapped[float | None] = mapped_column(Numeric)
    evaluation_status: Mapped[str] = mapped_column(String(20), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ExecutiveServiceHealth(UUIDPrimaryKey, Base):
    __tablename__ = "service_health"
    __table_args__ = (Index("ix_service_health_code", "service_code"), Index("ix_service_health_checked", "checked_at"), {"schema": "executive"})
    service_code: Mapped[str] = mapped_column(String(100), nullable=False)
    service_name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_time_ms: Mapped[float | None] = mapped_column(Numeric(12, 3))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MergeBatch(UUIDPrimaryKey, Base):
    __tablename__ = "merge_batches"
    __table_args__ = (
        UniqueConstraint("batch_code", name="uq_merge_batches_batch_code"),
        Index("ix_merge_batches_entity_status", "entity_type", "status"),
        {"schema": "staging"},
    )
    batch_code: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    excel_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    excel_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    kml_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    kml_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    excel_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    kml_record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    matching_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    created_by: Mapped[str | None] = mapped_column(String(150))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    proposals: Mapped[list["MergeProposal"]] = relationship(back_populates="batch", lazy="selectin", cascade="all, delete-orphan")


class MergeProposal(UUIDPrimaryKey, Base):
    __tablename__ = "merge_proposals"
    __table_args__ = (
        UniqueConstraint("batch_id", "excel_record_id", "kml_record_id", name="uq_merge_proposal_pair"),
        Index("ix_merge_proposals_batch_status", "batch_id", "review_status"),
        Index("ix_merge_proposals_candidate_class", "candidate_class"),
        Index("ix_merge_proposals_conflict_severity", "conflict_severity"),
        Index("ix_merge_proposals_conflict_fields_gin", "conflict_fields", postgresql_using="gin"),
        {"schema": "staging"},
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_batches.id", ondelete="CASCADE"), nullable=False)
    excel_record_id: Mapped[str] = mapped_column(String(150), nullable=False)
    kml_record_id: Mapped[str] = mapped_column(String(150), nullable=False)
    excel_name: Mapped[str | None] = mapped_column(Text)
    kml_name: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    name_similarity: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    distance_meters: Mapped[float | None] = mapped_column(Numeric(12, 2))
    candidate_class: Mapped[str] = mapped_column(String(40), nullable=False)
    conflict_severity: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    conflict_fields: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    excel_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    kml_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    proposed_site: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    field_sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending_review")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    assigned_role: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    batch: Mapped[MergeBatch] = relationship(back_populates="proposals")
    decisions: Mapped[list["MergeDecision"]] = relationship(back_populates="proposal", lazy="selectin", cascade="all, delete-orphan", order_by="MergeDecision.decided_at")


class MergeDecision(UUIDPrimaryKey, Base):
    __tablename__ = "merge_decisions"
    __table_args__ = (Index("ix_merge_decisions_proposal", "proposal_id", "decided_at"), {"schema": "staging"})
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_proposals.id", ondelete="CASCADE"), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    review_stage: Mapped[str] = mapped_column(String(50), nullable=False, default="merge_review")
    reviewer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_reference: Mapped[str | None] = mapped_column(String(150))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    decision_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    proposal: Mapped[MergeProposal] = relationship(back_populates="decisions")
<<<<<<< HEAD


class MergeExecutionBatch(UUIDPrimaryKey, Base):
    __tablename__ = "merge_execution_batches"
    __table_args__ = (
        status_check("execution_mode", ("dry_run", "controlled_execution", "rollback_preview"), "merge_execution_batches_mode"),
        status_check("status", ("draft", "validated", "blocked", "approved_for_execution", "running", "completed", "completed_with_errors", "failed", "cancelled", "rolled_back"), "merge_execution_batches_status"),
        UniqueConstraint("execution_code", name="uq_merge_execution_batches_code"),
        Index("ix_merge_execution_batches_merge_batch", "merge_batch_id", "status"),
        {"schema": "staging"},
    )
    execution_code: Mapped[str] = mapped_column(String(160), nullable=False)
    merge_batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_batches.id"), nullable=False)
    requested_proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    executed_proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_proposal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="dry_run")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    requested_by_role: Mapped[str] = mapped_column(String(100), nullable=False)
    requested_by_reference: Mapped[str | None] = mapped_column(String(150))
    dry_run_report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    items: Mapped[list["MergeExecutionItem"]] = relationship(back_populates="execution_batch", lazy="selectin", cascade="all, delete-orphan")


class MergeExecutionItem(UUIDPrimaryKey, Base):
    __tablename__ = "merge_execution_items"
    __table_args__ = (
        status_check("operation_type", ("create_national_site", "update_existing_site", "keep_separate", "no_operation"), "merge_execution_items_operation"),
        status_check("execution_status", ("pending", "eligible", "blocked", "executing", "completed", "failed", "skipped", "rolled_back"), "merge_execution_items_status"),
        UniqueConstraint("execution_batch_id", "proposal_id", name="uq_merge_execution_item_proposal"),
        Index("ix_merge_execution_items_proposal_status", "proposal_id", "execution_status"),
        {"schema": "staging"},
    )
    execution_batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_execution_batches.id", ondelete="CASCADE"), nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_proposals.id"), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_site_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atlas.sites.id"))
    target_national_id: Mapped[str | None] = mapped_column(String(100))
    pre_merge_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    proposed_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    field_merge_plan: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    execution_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    execution_batch: Mapped[MergeExecutionBatch] = relationship(back_populates="items")


class MergeExecutionEvent(UUIDPrimaryKey, Base):
    __tablename__ = "merge_execution_events"
    __table_args__ = (Index("ix_merge_execution_events_batch_time", "execution_batch_id", "occurred_at"), {"schema": "audit"})
    execution_batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("staging.merge_execution_batches.id", ondelete="CASCADE"), nullable=False)
    execution_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staging.merge_execution_items.id", ondelete="CASCADE"))
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("staging.merge_proposals.id"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_reference: Mapped[str | None] = mapped_column(String(150))
    event_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
=======
>>>>>>> origin/main
