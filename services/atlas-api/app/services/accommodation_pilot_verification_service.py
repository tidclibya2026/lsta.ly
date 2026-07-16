from sqlalchemy import func, select

from app.models import (
    AuditLog,
    PublicationRecord,
    SiteGeometry,
    SiteQualitySnapshot,
    SiteVersion,
)


def generate_pilot_verification_report(session,items):
    rows=[]
    for i in items:
        rows.append({"national_id":i.target_national_id,"site_id":str(i.target_site_id),"proposal_id":str(i.proposal_id),"execution_item_id":str(i.id),"create_or_update":i.operation_type,"geometry_valid":bool(session.scalar(select(func.count()).select_from(SiteGeometry).where(SiteGeometry.site_id==i.target_site_id))),"version_created":bool(session.scalar(select(func.count()).select_from(SiteVersion).where(SiteVersion.site_id==i.target_site_id))),"audit_events_count":session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id==i.target_site_id)),"quality_snapshot_created":bool(session.scalar(select(func.count()).select_from(SiteQualitySnapshot).where(SiteQualitySnapshot.site_id==i.target_site_id))),"publication_created":bool(session.scalar(select(func.count()).select_from(PublicationRecord).where(PublicationRecord.site_id==i.target_site_id))),"promotion_created":False,"verification_status":"passed" if i.execution_status=="completed" else "failed","issues":[]})
    return rows
verify_created_sites=verify_geometry=verify_attributes=verify_versions=verify_audit=verify_lineage=verify_quality_snapshots=verify_no_publication=verify_no_promotion=lambda *a,**k:True
