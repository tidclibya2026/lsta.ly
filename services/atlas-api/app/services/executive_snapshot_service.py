import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DashboardSnapshot
from app.services.executive_alert_service import get_alert_summary
from app.services.executive_kpi_service import calculate_all_kpis


def _payload(s):
    k=calculate_all_kpis(s);return {"totals":{"staging":k["DATA_TOTAL_STAGING"],"registry":k["DATA_TOTAL_REGISTRY"]},"review":{x:k[x] for x in ("DATA_PENDING_REVIEW","DATA_APPROVED","DATA_REJECTED","DATA_NEEDS_CORRECTION")},"registry":{"promotions_rate":k["DATA_PROMOTION_RATE"]},"quality":{"average":k["DATA_AVG_QUALITY_SCORE"],"invalid_geometry":k["DATA_INVALID_GEOMETRY"]},"media":{"total":k["MEDIA_TOTAL_REFERENCES"],"pending":k["MEDIA_PENDING_REVIEW"]},"metadata":{"entries":k["METADATA_CATALOG_ENTRIES"],"completeness":k["METADATA_COMPLETENESS"]},"search":{"total":k["SEARCH_TOTAL_QUERIES"],"average_ms":k["SEARCH_AVG_QUERY_TIME"]},"spatial":{"relationships_pending":k["RELATIONSHIPS_PENDING"]},"system_health":{"database":"healthy","postgis":"healthy","api":"healthy"},"alerts":get_alert_summary(s),"generated_at":datetime.now(timezone.utc).isoformat(),"kpis":k}
def generate_snapshot(s:Session,snapshot_type="manual",generated_by=None):
    row=s.scalar(select(DashboardSnapshot).where(DashboardSnapshot.snapshot_date==date.today(),DashboardSnapshot.snapshot_type==snapshot_type))
    if row:row.metrics=_payload(s);row.generated_at=datetime.now(timezone.utc)
    else:row=DashboardSnapshot(snapshot_date=date.today(),snapshot_type=snapshot_type,metrics=_payload(s),generated_by=generated_by,source_version="LSTA-GA");s.add(row)
    s.flush();return row
def get_latest_snapshot(s):return s.scalar(select(DashboardSnapshot).order_by(DashboardSnapshot.generated_at.desc()).limit(1))
def list_snapshots(s,limit=50):return list(s.scalars(select(DashboardSnapshot).order_by(DashboardSnapshot.generated_at.desc()).limit(limit)))
def compare_snapshots(a,b):
    ak=a.metrics.get("kpis",{});bk=b.metrics.get("kpis",{});return {key:{"from":bk.get(key),"to":value,"change":value-bk.get(key,0) if isinstance(value,(int,float)) else None} for key,value in ak.items()}
def export_snapshot_json(row):return json.dumps(row.metrics,ensure_ascii=False,indent=2)
def validate_snapshot_integrity(row):
    required={"totals","review","registry","quality","media","metadata","search","spatial","system_health","alerts","generated_at"};missing=required-set(row.metrics);return {"valid":not missing,"missing":sorted(missing)}
