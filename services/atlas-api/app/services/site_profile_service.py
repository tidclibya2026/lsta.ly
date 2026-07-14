from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaAsset, SiteAttribute, SiteDocument, SiteProfile


def get_profile(session: Session, site_id: uuid.UUID, *, create: bool = True) -> SiteProfile | None:
    profile = session.scalar(select(SiteProfile).where(SiteProfile.site_id == site_id))
    if profile is None and create:
        profile = SiteProfile(site_id=site_id)
        session.add(profile)
        session.flush()
    return profile


def create_or_update_profile(session: Session, site_id: uuid.UUID, values: dict[str, Any]) -> SiteProfile:
    profile = get_profile(session, site_id, create=True)
    assert profile is not None
    allowed = {column.name for column in SiteProfile.__table__.columns} - {"id", "site_id", "created_at", "updated_at"}
    for key, value in values.items():
        if key in allowed:
            setattr(profile, key, value)
    session.flush()
    return profile


def list_attributes(session: Session, site_id: uuid.UUID) -> list[SiteAttribute]:
    return list(
        session.scalars(
            select(SiteAttribute)
            .where(SiteAttribute.site_id == site_id)
            .order_by(SiteAttribute.display_order, SiteAttribute.attribute_group)
        )
    )


def upsert_attribute(session: Session, site_id: uuid.UUID, attribute_key: str, values: dict[str, Any]) -> SiteAttribute:
    group = str(values.get("attribute_group") or "general")
    item = session.scalar(
        select(SiteAttribute).where(
            SiteAttribute.site_id == site_id,
            SiteAttribute.attribute_group == group,
            SiteAttribute.attribute_key == attribute_key,
        )
    )
    if item is None:
        item = SiteAttribute(
            site_id=site_id,
            attribute_group=group,
            attribute_key=attribute_key,
            label_ar=str(values.get("label_ar") or attribute_key),
        )
        session.add(item)
    allowed = {column.name for column in SiteAttribute.__table__.columns} - {
        "id",
        "site_id",
        "attribute_key",
        "created_at",
        "updated_at",
    }
    for key, value in values.items():
        if key in allowed:
            setattr(item, key, value)
    session.flush()
    return item


def delete_attribute(session: Session, site_id: uuid.UUID, attribute_key: str) -> None:
    item = session.scalar(
        select(SiteAttribute).where(SiteAttribute.site_id == site_id, SiteAttribute.attribute_key == attribute_key)
    )
    if item is None:
        raise LookupError("الخاصية غير موجودة")
    session.delete(item)


def list_media(session: Session, site_id: uuid.UUID) -> list[MediaAsset]:
    return list(
        session.scalars(select(MediaAsset).where(MediaAsset.site_id == site_id).order_by(MediaAsset.display_order))
    )


def list_documents(session: Session, site_id: uuid.UUID) -> list[SiteDocument]:
    return list(
        session.scalars(
            select(SiteDocument).where(SiteDocument.site_id == site_id).order_by(SiteDocument.created_at.desc())
        )
    )


def create_document_metadata(session: Session, site_id: uuid.UUID, values: dict[str, Any]) -> SiteDocument:
    document = SiteDocument(site_id=site_id, **values)
    session.add(document)
    session.flush()
    return document


def delete_document_metadata(session: Session, site_id: uuid.UUID, document_id: uuid.UUID) -> None:
    document = session.get(SiteDocument, document_id)
    if document is None or document.site_id != site_id:
        raise LookupError("الوثيقة غير موجودة")
    session.delete(document)
