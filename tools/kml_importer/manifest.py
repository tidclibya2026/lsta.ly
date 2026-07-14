from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .models import AtlasFeature, ImportManifest
from .parser import sha256_file


def build_manifest(path: Path, source_id: str, features: list[AtlasFeature]) -> ImportManifest:
    counts: Counter[str] = Counter()
    for feature in features:
        _count_geometry(feature.geometry, counts)
    issue_count = sum(len(feature.quality_issues) for feature in features)
    return ImportManifest(
        source_id=source_id,
        source_file=path.name,
        source_sha256=sha256_file(path),
        imported_at=datetime.now(timezone.utc),
        feature_count=len(features),
        point_count=counts["Point"],
        line_count=counts["LineString"],
        polygon_count=counts["Polygon"],
        image_count=sum(len(feature.image_urls) for feature in features),
        unnamed_count=sum(not feature.name_ar for feature in features),
        without_description_count=sum(not feature.description_html for feature in features),
        invalid_coordinate_count=sum(
            any(issue.startswith(("invalid_coordinate:", "invalid_geometry:")) for issue in feature.quality_issues)
            for feature in features
        ),
        named_features=sum(bool(feature.name_ar) for feature in features),
        unnamed_points=sum(not feature.name_ar and feature.geometry_type == "Point" for feature in features),
        unnamed_lines=sum(not feature.name_ar and feature.geometry_type == "LineString" for feature in features),
        unnamed_polygons=sum(not feature.name_ar and feature.geometry_type == "Polygon" for feature in features),
        features_with_images=sum(bool(feature.image_urls) for feature in features),
        features_with_extended_data=sum(bool(feature.extended_data) for feature in features),
        status="success_with_issues" if issue_count else "success",
    )


def _count_geometry(geometry: dict[str, object] | None, counts: Counter[str]) -> None:
    if not geometry:
        return
    kind = str(geometry.get("type", "Unknown"))
    if kind == "GeometryCollection":
        for child in geometry.get("geometries", []):
            if isinstance(child, dict):
                _count_geometry(child, counts)
    else:
        counts[kind] += 1
