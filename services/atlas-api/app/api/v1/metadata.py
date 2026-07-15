from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models import DataLineageNode
from app.services import data_lineage_service as lineage
from app.services import metadata_catalog_service as catalog
from app.services import metadata_quality_service as quality

router = APIRouter(prefix="/api/v1/metadata", tags=["metadata-catalog"])
Role = Annotated[str, Depends(get_reviewer_role)]


def _write(role: str, allowed: set[str]):
    if role not in allowed | {"system_admin"}:
        raise HTTPException(403, "لا توجد صلاحية")


def _entry(e, details=False):
    value = {
        "catalog_code": e.catalog_code,
        "entry_type": e.entry_type,
        "title_ar": e.title_ar,
        "title_en": e.title_en,
        "description_ar": e.description_ar,
        "classification_level": e.classification_level,
        "sensitivity_level": e.sensitivity_level,
        "lifecycle_status": e.lifecycle_status,
        "verification_status": e.verification_status,
        "publication_status": e.publication_status,
        "source_system": e.source_system,
        "source_reference": e.source_reference,
        "keywords": e.keywords,
        "tags": e.tags,
        "completeness": catalog.calculate_catalog_completeness(e),
    }
    if details:
        value.update(
            {
                "owning_organization": e.owning_organization,
                "metadata_standard": e.metadata_standard,
                "metadata_json": e.metadata_json,
            }
        )
    return value


def _graph(value):
    return {
        "nodes": [
            {
                "id": str(n.id),
                "type": n.node_type,
                "reference": n.node_reference,
                "title": n.title,
                "system": n.system_name,
            }
            for n in value["nodes"]
        ],
        "edges": [
            {
                "id": str(e.id),
                "source": str(e.source_node_id),
                "target": str(e.target_node_id),
                "type": e.transformation_type,
                "status": e.status,
                "executed_at": e.executed_at,
            }
            for e in value["edges"]
        ],
    }


def _node(db, node_type, node_reference):
    node = db.scalar(
        select(DataLineageNode).where(
            DataLineageNode.node_type == node_type, DataLineageNode.node_reference == node_reference
        )
    )
    if not node:
        raise HTTPException(404, "عقدة lineage غير موجودة")
    return node


@router.get("/catalog")
def entries(
    role: Role,
    search: str | None = None,
    entry_type: str | None = None,
    classification_level: str | None = None,
    limit: int = Query(25, le=100, ge=1),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    allowed = (
        ("public", "internal", "restricted", "confidential")
        if role in {"data_manager", "system_admin"}
        else ("public", "internal")
    )
    items, total = catalog.list_catalog_entries(
        db,
        search=search,
        entry_type=entry_type,
        classification_level=classification_level,
        limit=limit,
        offset=offset,
        allowed_classifications=allowed,
    )
    return {"items": [_entry(e) for e in items], "total": total, "limit": limit, "offset": offset}


@router.post("/catalog", status_code=201)
def create(data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"data_manager"})
    e = catalog.create_catalog_entry(db, data)
    db.commit()
    return _entry(e, True)


@router.get("/catalog/{code}")
def detail(code: str, role: Role, db: Session = Depends(get_db)):
    try:
        e = catalog.get_catalog_entry(db, code)
    except LookupError:
        raise HTTPException(404, "الأصل الوصفي غير موجود") from None
    if e.classification_level in {"restricted", "confidential"} and role not in {"data_manager", "system_admin"}:
        raise HTTPException(404, "الأصل الوصفي غير موجود")
    return _entry(e, True)


@router.patch("/catalog/{code}")
def update(code: str, data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"editor", "data_manager"})
    e = catalog.update_catalog_entry(db, code, data)
    db.commit()
    return _entry(e, True)


@router.post("/catalog/{code}/archive")
def archive(code: str, role: Role, db: Session = Depends(get_db)):
    _write(role, {"data_manager"})
    e = catalog.archive_catalog_entry(db, code)
    db.commit()
    return _entry(e, True)


@router.get("/catalog/{code}/fields")
def fields(code: str, role: Role, db: Session = Depends(get_db)):
    e = catalog.get_catalog_entry(db, code)
    return [
        {c.name: getattr(f, c.name) for c in f.__table__.columns if c.name not in {"catalog_entry_id"}}
        for f in catalog.list_catalog_fields(db, e.id)
    ]


@router.put("/catalog/{code}/fields/{field_name}")
def field_put(code: str, field_name: str, data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"editor", "data_manager"})
    e = catalog.get_catalog_entry(db, code)
    f = catalog.upsert_catalog_field(db, e.id, field_name, data)
    db.commit()
    return {c.name: getattr(f, c.name) for c in f.__table__.columns}


@router.delete("/catalog/{code}/fields/{field_name}", status_code=204)
def field_delete(code: str, field_name: str, role: Role, db: Session = Depends(get_db)):
    _write(role, {"data_manager"})
    e = catalog.get_catalog_entry(db, code)
    catalog.delete_catalog_field(db, e.id, field_name)
    db.commit()


@router.get("/catalog/{code}/versions")
def versions(code: str, role: Role, db: Session = Depends(get_db)):
    e = catalog.get_catalog_entry(db, code)
    return [{c.name: getattr(v, c.name) for c in v.__table__.columns} for v in catalog.list_dataset_versions(db, e.id)]


@router.post("/catalog/{code}/versions", status_code=201)
def version_create(code: str, data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"data_manager"})
    e = catalog.get_catalog_entry(db, code)
    v = catalog.create_dataset_version(db, e.id, data)
    db.commit()
    return {c.name: getattr(v, c.name) for c in v.__table__.columns}


@router.get("/lineage/{node_type}/{node_reference}")
def graph(
    node_type: str, node_reference: str, role: Role, depth: int = Query(3, ge=0, le=10), db: Session = Depends(get_db)
):
    return _graph(lineage.get_full_lineage_graph(db, _node(db, node_type, node_reference).id, depth))


@router.get("/lineage/{node_type}/{node_reference}/upstream")
def upstream(
    node_type: str, node_reference: str, role: Role, depth: int = Query(3, ge=0, le=10), db: Session = Depends(get_db)
):
    return _graph(lineage.trace_upstream(db, _node(db, node_type, node_reference).id, depth))


@router.get("/lineage/{node_type}/{node_reference}/downstream")
def downstream(
    node_type: str, node_reference: str, role: Role, depth: int = Query(3, ge=0, le=10), db: Session = Depends(get_db)
):
    return _graph(lineage.trace_downstream(db, _node(db, node_type, node_reference).id, depth))


@router.get("/quality/rules")
def rules(role: Role, db: Session = Depends(get_db)):
    return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in quality.list_rules(db)]


@router.post("/quality/rules", status_code=201)
def rule_create(data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"data_manager"})
    r = quality.create_rule(db, data)
    db.commit()
    return {"rule_code": r.rule_code}


@router.post("/quality/evaluate")
def evaluate(data: dict[str, Any], role: Role, db: Session = Depends(get_db)):
    _write(role, {"reviewer", "data_manager"})
    items = quality.execute_rules_for_entity(db, data["entity_type"], data["entity_id"], data.get("values", {}), role)
    db.commit()
    return {"evaluated": len(items)}


@router.get("/quality/results")
def results(role: Role, entity_type: str | None = None, db: Session = Depends(get_db)):
    return [
        {
            "id": str(r.id),
            "entity_type": r.entity_type,
            "entity_id": r.entity_id,
            "status": r.status,
            "score": float(r.score) if r.score is not None else None,
        }
        for r in quality.get_quality_results(db, entity_type)
    ]


@router.get("/quality/summary")
def summary(role: Role, db: Session = Depends(get_db)):
    return quality.get_quality_summary(db)
