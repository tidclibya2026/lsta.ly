from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from geoalchemy2.shape import from_shape
from shapely import force_2d
from shapely.geometry import shape
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.session import create_database_engine, session_factory
from app.models import AuditLog, DataSource, ImportBatch, ImportFeature


class DuplicateSourceError(RuntimeError):
    pass


def load_inputs(geojson_path: Path, manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if geojson.get("type") != "FeatureCollection" or not isinstance(geojson.get("features"), list):
        raise ValueError("ملف GeoJSON ليس FeatureCollection صالحًا")
    if not manifest.get("source_sha256"):
        raise ValueError("ملف manifest لا يحتوي source_sha256")
    return geojson, manifest


def guard_duplicate(existing: DataSource | None, force: bool) -> None:
    if existing is not None and not force:
        raise DuplicateSourceError(f"المصدر ذو البصمة {existing.sha256} مستورد مسبقًا؛ استخدم --force لإعادة بنائه")


def build_staging_features(features: list[dict[str, Any]], batch_id: uuid.UUID) -> list[ImportFeature]:
    records: list[ImportFeature] = []
    for index, feature in enumerate(features, start=1):
        geometry_data = feature.get("geometry")
        if not geometry_data:
            raise ValueError(f"العنصر {index} بلا هندسة")
        properties = feature.get("properties") or {}
        source_feature_id = str(properties.get("feature_id") or feature.get("id") or f"UNKNOWN-{index:06d}")
        name_ar = str(properties.get("name_ar") or "").strip() or None
        validation_issues = properties.get("quality_issues") or []
        geometry = force_2d(shape(geometry_data))
        records.append(
            ImportFeature(
                batch_id=batch_id,
                source_feature_id=source_feature_id,
                name_ar=name_ar,
                geometry_type=geometry.geom_type,
                geometry=from_shape(geometry, srid=4326),
                properties=properties,
                validation_issues=validation_issues,
                missing_name=name_ar is None,
                review_status="pending_review",
            )
        )
    return records


def complete_batch_transaction(
    factory: sessionmaker[Session], batch_id: uuid.UUID, records: list[ImportFeature], checksum: str
) -> None:
    with factory.begin() as session:
        session.add_all(records)
        batch = session.get(ImportBatch, batch_id)
        if batch is None:
            raise RuntimeError("تعذر العثور على دفعة الاستيراد")
        batch.status = "completed"
        batch.imported_count = len(records)
        batch.completed_at = datetime.now(timezone.utc)
        session.add(
            AuditLog(
                action="staging_import_completed",
                entity_type="import_batch",
                entity_id=batch_id,
                details={"source_sha256": checksum, "feature_count": len(records), "target": "staging.import_features"},
            )
        )


def import_old_tripoli(
    geojson_path: Path,
    manifest_path: Path,
    factory: sessionmaker[Session],
    *,
    force: bool = False,
    feature_builder: Callable[[list[dict[str, Any]], uuid.UUID], list[ImportFeature]] = build_staging_features,
) -> dict[str, Any]:
    geojson, manifest = load_inputs(geojson_path, manifest_path)
    checksum = str(manifest["source_sha256"])
    with factory() as session:
        existing = session.scalar(select(DataSource).where(DataSource.sha256 == checksum))
        guard_duplicate(existing, force)
        if existing is not None:
            batch_ids = list(session.scalars(select(ImportBatch.id).where(ImportBatch.data_source_id == existing.id)))
            if batch_ids:
                session.execute(delete(ImportFeature).where(ImportFeature.batch_id.in_(batch_ids)))
                session.execute(delete(ImportBatch).where(ImportBatch.id.in_(batch_ids)))
            source = existing
            source.manifest = manifest
        else:
            source = DataSource(
                name="المدينة القديمة طرابلس",
                source_file=geojson_path.name,
                source_type="geojson",
                sha256=checksum,
                manifest=manifest,
            )
            session.add(source)
            session.flush()
        batch = ImportBatch(
            data_source_id=source.id, status="running", feature_count=len(geojson["features"]), imported_count=0
        )
        session.add(batch)
        session.commit()
        batch_id = batch.id

    try:
        records = feature_builder(geojson["features"], batch_id)
        complete_batch_transaction(factory, batch_id, records, checksum)
    except Exception as exc:
        with factory.begin() as session:
            batch = session.get(ImportBatch, batch_id)
            if batch is not None:
                batch.status = "failed"
                batch.error_message = str(exc)[:4000]
                batch.completed_at = datetime.now(timezone.utc)
        raise

    with factory() as session:
        distribution = dict(
            session.execute(
                select(ImportFeature.geometry_type, func.count())
                .where(ImportFeature.batch_id == batch_id)
                .group_by(ImportFeature.geometry_type)
            ).all()
        )
    return {
        "batch_id": str(batch_id),
        "source_sha256": checksum,
        "imported_count": len(records),
        "geometry_types": distribution,
        "status": "completed",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="استيراد المدينة القديمة طرابلس إلى Staging في منصة LSTA")
    parser.add_argument("--geojson", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--force", action="store_true", help="إعادة بناء دفعات المصدر نفسه دون إنشاء data_source مكرر")
    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args()
    engine = create_database_engine(get_settings().database_url)
    try:
        result = import_old_tripoli(args.geojson, args.manifest, session_factory(engine), force=args.force)
    except DuplicateSourceError as exc:
        print(f"رفض الاستيراد المكرر: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
