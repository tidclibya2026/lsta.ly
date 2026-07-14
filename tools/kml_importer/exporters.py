from __future__ import annotations

import csv
import json
from pathlib import Path

from .missing_names import write_missing_names_analysis
from .models import AtlasFeature, ImportResult


def export_result(result: ImportResult, output_dir: Path, basename: str, report_path: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{basename}.json"
    geojson_path = output_dir / f"{basename}.geojson"
    csv_path = output_dir / f"{basename}.csv"
    manifest_path = output_dir / f"{basename}_manifest.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    manifest_path.write_text(result.manifest.model_dump_json(indent=2), encoding="utf-8")
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": feature.feature_id,
                "geometry": feature.geometry,
                "properties": feature.model_dump(exclude={"geometry", "coordinates"}, mode="json"),
            }
            for feature in result.features
        ],
    }
    geojson_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(csv_path, result)
    from .quality import markdown_report

    report_path.write_text(markdown_report(result), encoding="utf-8")
    review_paths = write_missing_names_analysis(result.features, report_path.parent, basename)
    return [geojson_path, csv_path, json_path, manifest_path, report_path, *review_paths]


def _write_csv(path: Path, result: ImportResult) -> None:
    fields = list(AtlasFeature.model_fields)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for feature in result.features:
            row = feature.model_dump(mode="json")
            writer.writerow({key: _cell(value) for key, value in row.items()})


def _cell(value: object) -> object:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list)) else value
