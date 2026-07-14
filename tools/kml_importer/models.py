from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AtlasFeature(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    feature_id: str
    name_ar: str = ""
    name_en: str = ""
    description_html: str = ""
    description_text: str = ""
    description_tables: dict[str, str] = Field(default_factory=dict)
    description_links: list[str] = Field(default_factory=list)
    description_unknown: list[str] = Field(default_factory=list)
    geometry_type: str = "Unknown"
    coordinates: Any = None
    geometry: dict[str, Any] | None = None
    folder_name: str = ""
    extended_data: dict[str, str] = Field(default_factory=dict)
    image_urls: list[str] = Field(default_factory=list)
    source_file: str
    source_sha256: str
    verification_status: Literal["unverified", "under_review", "verified"] = "unverified"
    quality_issues: list[str] = Field(default_factory=list)
    style_url: str = ""
    icon_url: str = ""
    color: str = ""


class ImportManifest(BaseModel):
    source_id: str
    source_file: str
    source_sha256: str
    imported_at: datetime
    feature_count: int
    point_count: int
    line_count: int
    polygon_count: int
    image_count: int
    unnamed_count: int
    without_description_count: int
    invalid_coordinate_count: int
    named_features: int
    unnamed_points: int
    unnamed_lines: int
    unnamed_polygons: int
    features_with_images: int
    features_with_extended_data: int
    status: Literal["success", "success_with_issues", "failed"]


class ImportResult(BaseModel):
    manifest: ImportManifest
    features: list[AtlasFeature]
