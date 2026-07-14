from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class SiteUpdate(BaseModel):
    name_ar: str | None = Field(None, min_length=1, max_length=500)
    name_en: str | None = Field(None, max_length=500)
    description: str | None = None
    category_id: uuid.UUID | None = None
    municipality_id: uuid.UUID | None = None


class ProfileUpdate(BaseModel):
    short_description_ar: str | None = None
    short_description_en: str | None = None
    historical_period: str | None = None
    tourism_significance: str | None = None
    visitor_information: dict[str, Any] = Field(default_factory=dict)
    accessibility_information: dict[str, Any] = Field(default_factory=dict)
    opening_hours: dict[str, Any] = Field(default_factory=dict)
    contact_information: dict[str, Any] = Field(default_factory=dict)
    official_website: HttpUrl | None = None
    public_notes: str | None = None
    internal_notes: str | None = None


class AttributeUpdate(BaseModel):
    attribute_group: str = "general"
    label_ar: str
    label_en: str | None = None
    value_text: str | None = None
    value_number: float | None = None
    value_boolean: bool | None = None
    value_date: date | None = None
    value_json: dict[str, Any] | None = None
    unit: str | None = None
    source_reference: str | None = None
    verification_status: str = "draft"
    display_order: int = 0
    is_public: bool = False


class DocumentCreate(BaseModel):
    document_type: str
    title_ar: str
    title_en: str | None = None
    description: str | None = None
    file_name: str
    storage_path: str | None = None
    original_url: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    sha256: str | None = Field(None, min_length=64, max_length=64)
    document_date: date | None = None
    issuing_organization: str | None = None
    rights_status: str = "unknown"
    verification_status: str = "draft"
    publication_status: str = "internal"


class RelationshipCreate(BaseModel):
    target_type: Literal["registry", "staging"]
    target_id: str
    relationship_type: Literal[
        "nearby",
        "part_of",
        "contains",
        "related_to",
        "route_connection",
        "service_for",
        "investment_related",
        "heritage_related",
        "accommodation_nearby",
        "food_service_nearby",
        "airport_nearby",
        "administrative_relation",
    ]
    distance_meters: float | None = None
    relationship_metadata: dict[str, Any] = Field(default_factory=dict)


class NearbyRefresh(BaseModel):
    radius_meters: float = Field(1000, gt=0, le=100000)
    relationship_type: str = "nearby"
    source: Literal["registry", "staging", "all"] = "staging"
    limit: int = Field(25, ge=1, le=50)


class RelationshipReview(BaseModel):
    verified_by: uuid.UUID | None = None
