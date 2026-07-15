from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ExecutiveAlert

RULES={"HIGH_PENDING_REVIEW":("review","high","ارتفاع البيانات قيد المراجعة","عدد كبير من السجلات ما زال ينتظر المراجعة","DATA_PENDING_REVIEW",100),"MEDIA_RIGHTS_UNKNOWN":("media","warning","حقوق الوسائط غير مكتملة","توجد مراجع صور بلا توثيق حقوق مكتمل","MEDIA_MISSING_RIGHTS",1),"INVALID_GEOMETRY_EXISTS":("quality","critical","هندسة غير صالحة","توجد هندسات تتطلب تصحيحًا","DATA_INVALID_GEOMETRY",0),"SEARCH_NO_RESULTS_HIGH":("search","warning","ارتفاع البحث بلا نتائج","نسبة البحث بلا نتائج تجاوزت الحد","SEARCH_NO_RESULT_RATE",30),"LINEAGE_BROKEN":("metadata","high","فجوات في نسب البيانات","توجد عقد بيانات وصفية غير مرتبطة","LINEAGE_ORPHAN_NODES",0),"DUPLICATE_CANDIDATES_HIGH":("quality","warning","مرشحو تكرار مرتفعون","توجد مرشحات تكرار تحتاج مراجعة","DUPLICATE_CANDIDATES",10)}
def prevent_duplicate_open_alerts(s,code):return s.scalar(select(ExecutiveAlert).where(ExecutiveAlert.alert_code==code,ExecutiveAlert.status.in_(["open","acknowledged","in_progress"])))
def create_alert(s:Session,code:str,kind:str,severity:str,title:str,description:str,metric:str|None=None,value:float|None=None,threshold:float|None=None):
    existing=prevent_duplicate_open_alerts(s,code)
    if existing:return existing
    row=ExecutiveAlert(alert_code=code,alert_type=kind,severity=severity,title_ar=title,description_ar=description,metric_name=metric,metric_value=value,threshold_value=threshold);s.add(row);s.flush();return row
def evaluate_alert_rules(s:Session,kpis:dict):
    rows=[]
    for code,(kind,severity,title,desc,metric,threshold) in RULES.items():
        value=float(kpis.get(metric,0));trigger=value>threshold
        if trigger:rows.append(create_alert(s,code,kind,severity,title,desc,metric,value,threshold))
    return rows
def list_alerts(s,status=None):
    stmt=select(ExecutiveAlert).order_by(ExecutiveAlert.created_at.desc());return list(s.scalars(stmt.where(ExecutiveAlert.status==status) if status else stmt))
def _get(s,id):
    row=s.get(ExecutiveAlert,id)
    if not row:raise LookupError("alert not found")
    return row
def acknowledge_alert(s,id:UUID,actor:str):row=_get(s,id);row.status="acknowledged";row.acknowledged_by=actor;row.acknowledged_at=datetime.now(timezone.utc);return row
def assign_alert(s,id:UUID,role:str):row=_get(s,id);row.assigned_role=role;row.status="in_progress";return row
def resolve_alert(s,id:UUID,actor:str,notes:str|None=None):row=_get(s,id);row.status="resolved";row.resolved_by=actor;row.resolved_at=datetime.now(timezone.utc);row.resolution_notes=notes;return row
def dismiss_alert(s,id:UUID,notes:str|None=None):row=_get(s,id);row.status="dismissed";row.resolution_notes=notes;return row
def get_alert_summary(s):return dict(s.execute(select(ExecutiveAlert.severity,func.count()).where(ExecutiveAlert.status.not_in(["resolved","dismissed"])).group_by(ExecutiveAlert.severity)).all())
