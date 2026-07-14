from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    ImportBatch,
    ImportFeature,
    Municipality,
    PromotionRecord,
    Site,
    SiteCategory,
    SiteGeometry,
    VerificationRecord,
)
from app.services.review_service import calculate_promotion_eligibility


class PromotionNotAllowedError(RuntimeError):
    pass


def generate_national_id(session: Session) -> str:
    value = session.scalar(text("SELECT nextval('atlas.old_tripoli_national_id_seq')"))
    return f"LSTA-OLD-TRIPOLI-{int(value):06d}"


def promote_feature(
    session: Session, feature_id: uuid.UUID, *, promoted_by: uuid.UUID | None = None, fail_after_site: bool = False
) -> Site:
    transaction = session.begin_nested() if session.in_transaction() else session.begin()
    with transaction:
        feature = session.get(ImportFeature, feature_id, with_for_update=True)
        if feature is None:
            raise LookupError("سجل Staging غير موجود")
        existing = session.scalar(select(PromotionRecord).where(PromotionRecord.import_feature_id == feature_id))
        if existing is not None:
            raise PromotionNotAllowedError("تمت معالجة ترقية هذا السجل مسبقًا")
        eligibility = calculate_promotion_eligibility(session, feature_id)
        if not eligibility["eligible"]:
            raise PromotionNotAllowedError(f"السجل غير مؤهل للترقية: {eligibility['checks']}")
        batch = session.get(ImportBatch, feature.batch_id)
        if batch is None:
            raise RuntimeError("دفعة الاستيراد غير موجودة")
        national_id = feature.proposed_national_id or generate_national_id(session)
        if session.scalar(select(Site.id).where(Site.national_id == national_id)):
            raise PromotionNotAllowedError("المعرف الوطني مستخدم مسبقًا")
        category = (
            session.scalar(select(SiteCategory).where(SiteCategory.code == feature.proposed_category_code))
            if feature.proposed_category_code
            else None
        )
        municipality = (
            session.scalar(select(Municipality).where(Municipality.code == feature.proposed_municipality_code))
            if feature.proposed_municipality_code
            else None
        )
        props = feature.properties
        site = Site(
            national_id=national_id,
            name_ar=feature.name_ar or "",
            name_en=props.get("name_en") or None,
            description=props.get("description_text") or None,
            category_id=category.id if category else None,
            municipality_id=municipality.id if municipality else None,
            data_source_id=batch.data_source_id,
            verification_status="approved",
        )
        session.add(site)
        session.flush()
        if fail_after_site:
            raise RuntimeError("forced promotion failure")
        session.add(SiteGeometry(site_id=site.id, geometry_type=feature.geometry_type, geometry=feature.geometry))
        session.add(
            VerificationRecord(
                site_id=site.id, verification_status="approved", notes="اعتماد نهائي عبر دورة مراجعة Government Alpha"
            )
        )
        now = datetime.now(timezone.utc)
        snapshot: dict[str, Any] = {
            "national_id": national_id,
            "source_feature_id": feature.source_feature_id,
            "name_ar": feature.name_ar,
            "geometry_type": feature.geometry_type,
            "properties": props,
        }
        session.add(
            PromotionRecord(
                import_feature_id=feature.id,
                site_id=site.id,
                promoted_by=promoted_by,
                promoted_at=now,
                status="promoted",
                snapshot=snapshot,
            )
        )
        session.add(
            AuditLog(
                action="feature_promoted_to_national_registry",
                entity_type="site",
                entity_id=site.id,
                details={
                    "import_feature_id": str(feature.id),
                    "national_id": national_id,
                    "source": "staging.import_features",
                },
            )
        )
        feature.proposed_national_id = national_id
        feature.promotion_eligible = False
        feature.review_status = "accepted"
        session.flush()
        return site
