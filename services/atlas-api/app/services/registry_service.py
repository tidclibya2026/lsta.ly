from __future__ import annotations

import re
import unicodedata
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Municipality, PublicationRecord, Site, SiteCategory
from app.services.site_completeness_service import calculate_site_completeness
from app.services.site_version_service import create_version_snapshot


def build_slug(site: Site) -> str:
    text = unicodedata.normalize("NFKC", f"{site.name_ar}-{site.national_id}").strip().lower()
    return re.sub(r"[^\w\u0600-\u06ff]+", "-", text).strip("-")


def publication_status_query():
    return (
        select(PublicationRecord.publication_status)
        .where(PublicationRecord.site_id == Site.id)
        .order_by(PublicationRecord.published_at.desc().nullslast())
        .limit(1)
        .scalar_subquery()
    )


def list_registry_sites(
    session: Session,
    *,
    search: str | None = None,
    category: str | None = None,
    municipality: str | None = None,
    verification_status: str | None = None,
    publication_status: str | None = None,
    completeness_min: float | None = None,
    completeness_max: float | None = None,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[Site], int]:
    query: Select[tuple[Site]] = select(Site)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Site.name_ar.ilike(term), Site.name_en.ilike(term), Site.national_id.ilike(term)))
    if category:
        query = query.join(SiteCategory, Site.category_id == SiteCategory.id).where(SiteCategory.code == category)
    if municipality:
        query = query.join(Municipality, Site.municipality_id == Municipality.id).where(
            Municipality.code == municipality
        )
    if verification_status:
        query = query.where(Site.verification_status == verification_status)
    if publication_status:
        query = query.where(func.coalesce(publication_status_query(), "internal") == publication_status)
    if completeness_min is not None:
        query = query.where(func.coalesce(Site.profile_completeness_score, 0) >= completeness_min)
    if completeness_max is not None:
        query = query.where(func.coalesce(Site.profile_completeness_score, 0) <= completeness_max)
    total = int(session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    return list(session.scalars(query.order_by(Site.national_id).limit(min(limit, 100)).offset(offset))), total


def get_registry_site(session: Session, national_id: str) -> Site:
    site = session.scalar(select(Site).where(Site.national_id == national_id))
    if site is None:
        raise LookupError("الموقع الوطني غير موجود")
    return site


def update_registry_site(session: Session, site: Site, values: dict[str, Any], *, role: str) -> Site:
    create_version_snapshot(session, site, "قبل تحديث بيانات السجل")
    allowed = {"name_ar", "name_en", "description", "category_id", "municipality_id"}
    for key, value in values.items():
        if key in allowed:
            setattr(site, key, value)
    if not site.slug:
        site.slug = build_slug(site)
    calculate_site_completeness(session, site, persist=True)
    session.add(
        AuditLog(
            action="registry_site_updated",
            entity_type="site",
            entity_id=site.id,
            details={"national_id": site.national_id, "role": role, "fields": sorted(set(values) & allowed)},
        )
    )
    session.flush()
    return site


def archive_registry_site(session: Session, site: Site, role: str) -> Site:
    create_version_snapshot(session, site, "قبل أرشفة الموقع")
    site.verification_status = "archived"
    session.add(
        AuditLog(
            action="registry_site_archived",
            entity_type="site",
            entity_id=site.id,
            details={"role": role, "national_id": site.national_id},
        )
    )
    return site


def restore_registry_site(session: Session, site: Site, role: str) -> Site:
    create_version_snapshot(session, site, "قبل استعادة الموقع")
    site.verification_status = "draft"
    session.add(
        AuditLog(
            action="registry_site_restored",
            entity_type="site",
            entity_id=site.id,
            details={"role": role, "national_id": site.national_id},
        )
    )
    return site
