from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CatalogEntry, CatalogField, DatasetVersion


def calculate_catalog_completeness(entry: CatalogEntry) -> int:
    fields = [
        entry.title_ar,
        entry.owning_organization,
        entry.entry_type,
        entry.description_ar,
        entry.source_system,
        entry.source_reference,
        entry.keywords,
    ]
    return round(sum(bool(value) for value in fields) / len(fields) * 100)


def list_catalog_entries(
    session: Session,
    *,
    search: str | None = None,
    entry_type: str | None = None,
    classification_level: str | None = None,
    limit: int = 25,
    offset: int = 0,
    allowed_classifications: tuple[str, ...] = ("public", "internal"),
) -> tuple[list[CatalogEntry], int]:
    stmt = select(CatalogEntry).where(CatalogEntry.classification_level.in_(allowed_classifications))
    if search:
        stmt = stmt.where(
            or_(
                CatalogEntry.catalog_code.ilike(f"%{search}%"),
                CatalogEntry.title_ar.ilike(f"%{search}%"),
                CatalogEntry.title_en.ilike(f"%{search}%"),
            )
        )
    if entry_type:
        stmt = stmt.where(CatalogEntry.entry_type == entry_type)
    if classification_level:
        stmt = stmt.where(CatalogEntry.classification_level == classification_level)
    total = int(session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    return list(session.scalars(stmt.order_by(CatalogEntry.catalog_code).offset(offset).limit(limit))), total


def search_catalog(session: Session, query: str, **kwargs: Any):
    return list_catalog_entries(session, search=query, **kwargs)


def get_catalog_entry(session: Session, code: str) -> CatalogEntry:
    entry = session.scalar(select(CatalogEntry).where(CatalogEntry.catalog_code == code))
    if not entry:
        raise LookupError(code)
    return entry


def create_catalog_entry(session: Session, data: dict[str, Any]) -> CatalogEntry:
    entry = CatalogEntry(**data)
    session.add(entry)
    session.flush()
    return entry


def update_catalog_entry(session: Session, code: str, data: dict[str, Any]) -> CatalogEntry:
    entry = get_catalog_entry(session, code)
    for key, value in data.items():
        if hasattr(entry, key) and key not in {"id", "catalog_code"}:
            setattr(entry, key, value)
    entry.updated_at = datetime.now(timezone.utc)
    session.flush()
    return entry


def archive_catalog_entry(session: Session, code: str) -> CatalogEntry:
    return update_catalog_entry(
        session, code, {"lifecycle_status": "archived", "archived_at": datetime.now(timezone.utc)}
    )


def list_catalog_fields(session: Session, entry_id):
    return list(
        session.scalars(
            select(CatalogField).where(CatalogField.catalog_entry_id == entry_id).order_by(CatalogField.display_order)
        )
    )


def upsert_catalog_field(session: Session, entry_id, field_name: str, data: dict[str, Any]) -> CatalogField:
    field = session.scalar(
        select(CatalogField).where(CatalogField.catalog_entry_id == entry_id, CatalogField.field_name == field_name)
    ) or CatalogField(
        catalog_entry_id=entry_id,
        field_name=field_name,
        label_ar=data.get("label_ar", field_name),
        data_type=data.get("data_type", "text"),
    )
    for key, value in data.items():
        if hasattr(field, key) and key not in {"id", "catalog_entry_id", "field_name"}:
            setattr(field, key, value)
    session.add(field)
    session.flush()
    return field


def delete_catalog_field(session: Session, entry_id, field_name: str) -> None:
    field = session.scalar(
        select(CatalogField).where(CatalogField.catalog_entry_id == entry_id, CatalogField.field_name == field_name)
    )
    if field:
        session.delete(field)
        session.flush()


def generate_schema_snapshot(session: Session, entry_id) -> dict[str, Any]:
    return {
        "fields": [
            {"name": f.field_name, "type": f.data_type, "nullable": f.nullable, "spatial": f.is_spatial}
            for f in list_catalog_fields(session, entry_id)
        ]
    }


def create_dataset_version(session: Session, entry_id, data: dict[str, Any]) -> DatasetVersion:
    if "version_number" not in data:
        data["version_number"] = (
            int(
                session.scalar(
                    select(func.coalesce(func.max(DatasetVersion.version_number), 0)).where(
                        DatasetVersion.catalog_entry_id == entry_id
                    )
                )
                or 0
            )
            + 1
        )
    data.setdefault("version_label", f"v{data['version_number']}")
    data.setdefault("schema_snapshot", generate_schema_snapshot(session, entry_id))
    version = DatasetVersion(catalog_entry_id=entry_id, **data)
    session.add(version)
    session.flush()
    return version


def list_dataset_versions(session: Session, entry_id):
    return list(
        session.scalars(
            select(DatasetVersion)
            .where(DatasetVersion.catalog_entry_id == entry_id)
            .order_by(DatasetVersion.version_number.desc())
        )
    )
