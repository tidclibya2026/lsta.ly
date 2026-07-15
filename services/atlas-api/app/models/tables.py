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
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
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
