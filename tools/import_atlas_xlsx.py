#!/usr/bin/env python3
"""Import Atlas Excel layers into PostgreSQL staging tables.

This module is intentionally conservative:
- it never writes directly to production tables;
- it preserves the source row as JSON;
- it calculates a SHA-256 file fingerprint;
- it records validation issues for human review;
- it does not automatically merge duplicate sites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import psycopg
import yaml

LOGGER = logging.getLogger("lsta.import")


@dataclass(frozen=True)
class LayerConfig:
    key: str
    code: str
    sheet: str | None
    sheet_candidates: tuple[str, ...]
    name_candidates: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def first_value(row: dict[str, Any], candidates: Iterable[str]) -> Any:
    for candidate in candidates:
        if candidate in row and clean_text(row[candidate]) is not None:
            return row[candidate]
    return None


def parse_float(value: Any) -> float | None:
    text = clean_text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def load_config(path: Path, layer_key: str) -> tuple[dict[str, Any], LayerConfig]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    layer = raw["layers"][layer_key]
    return raw, LayerConfig(
        key=layer_key,
        code=layer["code"],
        sheet=layer.get("sheet"),
        sheet_candidates=tuple(layer.get("sheet_candidates", [])),
        name_candidates=tuple(layer.get("name_candidates", ["الاسم"])),
    )


def choose_sheet(book: pd.ExcelFile, config: LayerConfig) -> str:
    if config.sheet and config.sheet in book.sheet_names:
        return config.sheet
    for candidate in config.sheet_candidates:
        if candidate in book.sheet_names:
            return candidate
    if len(book.sheet_names) == 1:
        return book.sheet_names[0]
    raise ValueError(
        f"Could not resolve sheet for {config.key}. Available: {book.sheet_names}"
    )


def validate_record(record: dict[str, Any], latitude: float | None, longitude: float | None) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    def add(code: str, severity: str, field: str, message: str, action: str) -> None:
        issues.append({
            "rule_code": code,
            "severity": severity,
            "field_name": field,
            "message_ar": message,
            "suggested_action_ar": action,
        })

    if not clean_text(record.get("source_record_id")):
        add("Q001", "error", "source_record_id", "المعرف المصدري مفقود.", "توليد أو استكمال معرف ثابت قبل الاعتماد.")
    if not clean_text(record.get("name_ar_raw")):
        add("Q002", "error", "name_ar_raw", "اسم الموقع مفقود.", "استكمال الاسم الرسمي والتحقق منه.")
    if latitude is None or not 19 <= latitude <= 34.5:
        add("Q003", "critical", "latitude_raw", "خط العرض غير صالح أو خارج النطاق المتوقع لليبيا.", "مراجعة الإحداثيات والمصدر في GIS.")
    if longitude is None or not 9 <= longitude <= 26:
        add("Q004", "critical", "longitude_raw", "خط الطول غير صالح أو خارج النطاق المتوقع لليبيا.", "مراجعة الإحداثيات والمصدر في GIS.")
    if not clean_text(record.get("municipality_raw")):
        add("Q005", "warning", "municipality_raw", "البلدية غير محددة.", "إسناد البلدية مكانيًا ثم مراجعتها بشريًا.")
    if not clean_text(record.get("source_files_raw")):
        add("Q006", "error", "source_files_raw", "المرجع المصدري غير موثق.", "إضافة اسم الملف أو الدراسة أو الجهة المالكة.")
    return issues


def import_file(
    conn: psycopg.Connection[Any],
    excel_path: Path,
    mapping_path: Path,
    layer_key: str,
    submitted_by: str,
    dry_run: bool,
) -> dict[str, Any]:
    mapping, config = load_config(mapping_path, layer_key)
    fingerprint = sha256_file(excel_path)
    book = pd.ExcelFile(excel_path)
    sheet = choose_sheet(book, config)
    frame = pd.read_excel(book, sheet_name=sheet, dtype=object)
    frame.columns = [clean_text(column) or f"unnamed_{index}" for index, column in enumerate(frame.columns)]

    result = {
        "file": excel_path.name,
        "layer": layer_key,
        "sheet": sheet,
        "rows": int(len(frame)),
        "sha256": fingerprint,
        "issues": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        for _, source_row in frame.iterrows():
            row = source_row.to_dict()
            lat = parse_float(row.get(mapping["common"]["latitude"]))
            lon = parse_float(row.get(mapping["common"]["longitude"]))
            record = {
                "source_record_id": row.get(mapping["common"]["source_id"]),
                "name_ar_raw": first_value(row, config.name_candidates),
                "municipality_raw": row.get(mapping["common"]["municipality"]),
                "source_files_raw": row.get(mapping["common"]["source_files"]),
            }
            result["issues"] += len(validate_record(record, lat, lon))
        return result

    with conn.transaction():
        batch_id = conn.execute(
            """
            INSERT INTO staging.import_batches
              (source_file_name, source_layer_code, source_sha256, source_row_count, submitted_by)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING batch_id
            """,
            (excel_path.name, config.code, fingerprint, len(frame), submitted_by),
        ).fetchone()[0]

        for source_index, source_row in frame.iterrows():
            row = source_row.to_dict()
            common = mapping["common"]
            lat_raw = row.get(common["latitude"])
            lon_raw = row.get(common["longitude"])
            record = {
                "source_record_id": clean_text(row.get(common["source_id"])),
                "layer_code": config.code,
                "name_ar_raw": clean_text(first_value(row, config.name_candidates)),
                "name_en_raw": clean_text(row.get(common["name_en"])),
                "municipality_raw": clean_text(row.get(common["municipality"])),
                "tourism_region_raw": clean_text(row.get(common["tourism_region"])),
                "latitude_raw": clean_text(lat_raw),
                "longitude_raw": clean_text(lon_raw),
                "national_category_raw": clean_text(row.get(common["national_category"])),
                "category_code_raw": clean_text(row.get(common["category_code"])),
                "subcategory_raw": clean_text(row.get(common["subcategory"])),
                "address_raw": clean_text(row.get(common["address"])),
                "phone_raw": clean_text(row.get(common["phone"])),
                "web_or_social_raw": clean_text(row.get(common["web_or_social"])),
                "description_raw": clean_text(row.get(common["description"])),
                "verification_status_raw": clean_text(row.get(common["verification_status"])),
                "verification_priority_raw": clean_text(row.get(common["verification_priority"])),
                "source_type_raw": clean_text(row.get(common["source_type"])),
                "source_files_raw": clean_text(row.get(common["source_files"])),
            }
            staging_id = conn.execute(
                """
                INSERT INTO staging.tourism_sites_raw (
                  batch_id, source_row_number, source_record_id, layer_code,
                  name_ar_raw, name_en_raw, municipality_raw, tourism_region_raw,
                  latitude_raw, longitude_raw, national_category_raw, category_code_raw,
                  subcategory_raw, address_raw, phone_raw, web_or_social_raw,
                  description_raw, verification_status_raw, verification_priority_raw,
                  source_type_raw, source_files_raw, raw_payload
                ) VALUES (
                  %(batch_id)s, %(source_row_number)s, %(source_record_id)s, %(layer_code)s,
                  %(name_ar_raw)s, %(name_en_raw)s, %(municipality_raw)s, %(tourism_region_raw)s,
                  %(latitude_raw)s, %(longitude_raw)s, %(national_category_raw)s, %(category_code_raw)s,
                  %(subcategory_raw)s, %(address_raw)s, %(phone_raw)s, %(web_or_social_raw)s,
                  %(description_raw)s, %(verification_status_raw)s, %(verification_priority_raw)s,
                  %(source_type_raw)s, %(source_files_raw)s, %(raw_payload)s::jsonb
                ) RETURNING staging_id
                """,
                {
                    **record,
                    "batch_id": batch_id,
                    "source_row_number": int(source_index) + 2,
                    "raw_payload": json.dumps({k: clean_text(v) for k, v in row.items()}, ensure_ascii=False),
                },
            ).fetchone()[0]

            latitude = parse_float(lat_raw)
            longitude = parse_float(lon_raw)
            issues = validate_record(record, latitude, longitude)
            result["issues"] += len(issues)
            for issue in issues:
                conn.execute(
                    """
                    INSERT INTO staging.validation_results
                      (staging_id, rule_code, severity, field_name, message_ar, suggested_action_ar)
                    VALUES (%(staging_id)s, %(rule_code)s, %(severity)s, %(field_name)s,
                            %(message_ar)s, %(suggested_action_ar)s)
                    """,
                    {"staging_id": staging_id, **issue},
                )

            completeness = 100.0 * sum(
                clean_text(record.get(field)) is not None
                for field in ("source_record_id", "name_ar_raw", "municipality_raw", "source_files_raw")
            ) / 4.0
            geom_wkt = f"SRID=4326;POINT({longitude} {latitude})" if latitude is not None and longitude is not None else None
            conn.execute(
                """
                INSERT INTO staging.normalized_sites (
                  staging_id, normalized_name_ar, normalized_name_en,
                  normalized_municipality_name, latitude, longitude, geom,
                  normalized_category_code, normalized_verification_status,
                  normalized_source_reference, completeness_score, spatial_valid
                ) VALUES (%s,%s,%s,%s,%s,%s,ST_GeomFromEWKT(%s),%s,%s,%s,%s,%s)
                """,
                (
                    staging_id, record["name_ar_raw"], record["name_en_raw"],
                    record["municipality_raw"], latitude, longitude, geom_wkt,
                    record["category_code_raw"] or config.code,
                    record["verification_status_raw"], record["source_files_raw"],
                    completeness,
                    latitude is not None and longitude is not None and 19 <= latitude <= 34.5 and 9 <= longitude <= 26,
                ),
            )

        conn.execute(
            "UPDATE staging.import_batches SET status = 'profiled' WHERE batch_id = %s",
            (batch_id,),
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Load an Atlas XLSX layer into staging.")
    parser.add_argument("excel", type=Path)
    parser.add_argument("--layer", required=True, choices=["hotels", "resorts_villages", "restaurants", "cafes", "thematic_layers"])
    parser.add_argument("--mapping", type=Path, default=Path("data/mappings/atlas_layers_v1.yml"))
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--submitted-by", default="TIDC Data Team")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level, format="%(levelname)s %(message)s")
    if not args.excel.exists():
        parser.error(f"Excel file not found: {args.excel}")
    if not args.mapping.exists():
        parser.error(f"Mapping file not found: {args.mapping}")
    if not args.dry_run and not args.database_url:
        parser.error("--database-url is required unless --dry-run is used")

    if args.dry_run:
        class NullConnection:
            pass
        result = import_file(NullConnection(), args.excel, args.mapping, args.layer, args.submitted_by, True)  # type: ignore[arg-type]
    else:
        with psycopg.connect(args.database_url) as conn:
            result = import_file(conn, args.excel, args.mapping, args.layer, args.submitted_by, False)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
