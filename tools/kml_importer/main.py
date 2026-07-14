from __future__ import annotations

from pathlib import Path

from .exporters import export_result
from .manifest import build_manifest
from .models import ImportResult
from .parser import parse_kml


def run_import(
    input_path: Path,
    output_dir: Path,
    report_path: Path,
    source_id: str = "SRC-2026-00001",
    feature_prefix: str = "LSTA-OLD-TRIPOLI",
    basename: str = "old_tripoli",
) -> tuple[ImportResult, list[Path]]:
    if input_path.suffix.lower() != ".kml":
        raise ValueError("المرحلة التجريبية الأولى تقبل ملفات KML فقط")
    features = parse_kml(input_path, source_id, feature_prefix)
    result = ImportResult(manifest=build_manifest(input_path, source_id, features), features=features)
    paths = export_result(result, output_dir, basename, report_path)
    return result, paths
