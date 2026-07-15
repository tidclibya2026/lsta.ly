from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_reviewer_role
from app.api.deps import get_db
from app.models import DashboardSnapshot, ExecutiveServiceHealth
from app.services.coverage_gap_service import (
    coverage_by_category,
    coverage_by_folder,
    coverage_by_geometry_type,
    coverage_by_municipality,
    identify_priority_areas,
    metadata_gaps,
)
from app.services.executive_alert_service import (
    acknowledge_alert,
    assign_alert,
    dismiss_alert,
    evaluate_alert_rules,
    get_alert_summary,
    list_alerts,
    resolve_alert,
)
from app.services.executive_kpi_service import calculate_all_kpis, get_kpi_trends, store_kpi_values
from app.services.executive_snapshot_service import (
    compare_snapshots,
    export_snapshot_json,
    generate_snapshot,
    get_latest_snapshot,
    list_snapshots,
    validate_snapshot_integrity,
)
from app.services.service_health_service import check_service_health

router=APIRouter(prefix="/api/v1/executive",tags=["executive-intelligence"]);Role=Annotated[str,Depends(get_reviewer_role)]
FULL={"decision_maker","data_manager","system_admin"};MANAGE={"data_manager","system_admin"}
class Action(BaseModel):notes:str|None=None;assigned_role:str|None=None
def serial(row):return {c.name:(str(v) if isinstance(v:=getattr(row,c.name),UUID) else float(v) if hasattr(v,"as_integer_ratio") and not isinstance(v,(int,float)) else v) for c in row.__table__.columns if c.name not in {"acknowledged_by","resolved_by"}}
def require(role,allowed):
    if role not in allowed:raise HTTPException(403,"لا توجد صلاحية لهذه البيانات التنفيذية")
@router.get("/summary")
def summary(role:Role,db:Session=Depends(get_db)):
    k=calculate_all_kpis(db);public={x:k[x] for x in ["DATA_TOTAL_STAGING","DATA_TOTAL_REGISTRY","DATA_PENDING_REVIEW","DATA_AVG_QUALITY_SCORE","DATA_AVG_COMPLETENESS","MEDIA_PENDING_REVIEW","DATA_INVALID_GEOMETRY"]}
    if role=="viewer":return {"kpis":public,"alerts":{},"system_health":"available","limited":True}
    return {"kpis":k,"alerts":get_alert_summary(db),"review_funnel":{"imported":k["DATA_TOTAL_STAGING"],"technical":0,"gis":0,"data":0,"final":0,"promoted":1,"published":0},"generated_at":"now"}
@router.get("/kpis")
def kpis(role:Role,db:Session=Depends(get_db)):return {"items":[{"code":code,"name_ar":code,"value":value,"evaluation_status":"good"} for code,value in calculate_all_kpis(db).items() if isinstance(value,(int,float))]}
@router.get("/kpis/{code}")
def kpi(code:str,role:Role,db:Session=Depends(get_db)):
    values=calculate_all_kpis(db)
    if code not in values:raise HTTPException(404,"المؤشر غير موجود")
    return {"code":code,"value":values[code]}
@router.get("/kpis/{code}/trend")
def trend(code:str,role:Role,days:int=Query(30,ge=1,le=365),db:Session=Depends(get_db)):return {"code":code,"period_days":days,"items":get_kpi_trends(db,code,days)}
@router.get("/alerts")
def alerts(role:Role,status:str|None=None,db:Session=Depends(get_db)):require(role,FULL|{"reviewer","gis_specialist"});return {"items":[serial(x) for x in list_alerts(db,status)]}
@router.get("/alerts/summary")
def alerts_summary(role:Role,db:Session=Depends(get_db)):require(role,FULL|{"reviewer","gis_specialist"});return get_alert_summary(db)
def _act(role,db,fn,*args):require(role,MANAGE);row=fn(db,*args);db.commit();return serial(row)
@router.post("/alerts/{id}/acknowledge")
def acknowledge(id:UUID,p:Action,role:Role,db:Session=Depends(get_db)):return _act(role,db,acknowledge_alert,id,role)
@router.post("/alerts/{id}/assign")
def assign(id:UUID,p:Action,role:Role,db:Session=Depends(get_db)):return _act(role,db,assign_alert,id,p.assigned_role or role)
@router.post("/alerts/{id}/resolve")
def resolve(id:UUID,p:Action,role:Role,db:Session=Depends(get_db)):return _act(role,db,resolve_alert,id,role,p.notes)
@router.post("/alerts/{id}/dismiss")
def dismiss(id:UUID,p:Action,role:Role,db:Session=Depends(get_db)):return _act(role,db,dismiss_alert,id,p.notes)
@router.get("/coverage")
def coverage(role:Role,db:Session=Depends(get_db)):require(role,FULL|{"gis_specialist"});return {"geometry_types":coverage_by_geometry_type(db),"folders":coverage_by_folder(db),"municipalities":coverage_by_municipality(db),"categories":coverage_by_category(db)}
@router.get("/gaps")
def gaps(role:Role,db:Session=Depends(get_db)):require(role,FULL|{"gis_specialist"});return {"items":identify_priority_areas(db),"metadata":metadata_gaps(db),"notice":"فجوة البيانات لا تعني غياب المقومات السياحية؛ بل تعكس نقص الحصر أو المراجعة."}
@router.get("/quality")
def quality(role:Role,db:Session=Depends(get_db)):require(role,FULL|{"reviewer","gis_specialist"});k=calculate_all_kpis(db);return {"average_quality":k["DATA_AVG_QUALITY_SCORE"],"average_completeness":k["DATA_AVG_COMPLETENESS"],"invalid_geometry":k["DATA_INVALID_GEOMETRY"]}
@router.get("/review-performance")
def review_performance(role:Role,db:Session=Depends(get_db)):require(role,FULL|{"reviewer"});return summary(role,db)
@router.get("/media-health")
def media_health(role:Role,db:Session=Depends(get_db)):require(role,FULL);k=calculate_all_kpis(db);return {x:k[x] for x in k if x.startswith("MEDIA_")}
@router.get("/metadata-health")
def metadata_health(role:Role,db:Session=Depends(get_db)):require(role,FULL);k=calculate_all_kpis(db);return {x:k[x] for x in k if x.startswith("METADATA_") or x.startswith("LINEAGE_")}
@router.get("/search-health")
def search_health(role:Role,db:Session=Depends(get_db)):require(role,FULL);k=calculate_all_kpis(db);return {x:k[x] for x in k if x.startswith("SEARCH_")}
@router.get("/service-health")
def service_health(role:Role,db:Session=Depends(get_db)):require(role,FULL);return {"items":check_service_health(db)}
@router.post("/snapshots",status_code=201)
def snapshot(role:Role,snapshot_type:Literal["daily","weekly","monthly","manual"]="manual",db:Session=Depends(get_db)):
    require(role,MANAGE);values=calculate_all_kpis(db);store_kpi_values(db,values);evaluate_alert_rules(db,values)
    for item in check_service_health(db):db.add(ExecutiveServiceHealth(service_code=item["service_code"],service_name=item["service_name"],status=item["status"],response_time_ms=item["response_time_ms"],details={"version":item["version"]}))
    row=generate_snapshot(db,snapshot_type,role);db.commit();db.refresh(row);return serial(row)
@router.get("/snapshots")
def snapshots(role:Role,db:Session=Depends(get_db)):require(role,FULL);return {"items":[serial(x) for x in list_snapshots(db)]}
@router.get("/snapshots/latest")
def latest(role:Role,export:Literal["json","none"]="none",db:Session=Depends(get_db)):
    require(role,FULL);row=get_latest_snapshot(db)
    if not row:raise HTTPException(404,"لا توجد لقطة")
    if export=="json":return Response(export_snapshot_json(row),media_type="application/json",headers={"Content-Disposition":"attachment; filename=lsta-executive-snapshot.json"})
    return {**serial(row),"integrity":validate_snapshot_integrity(row)}
@router.get("/snapshots/compare")
def compare(first:UUID,second:UUID,role:Role,db:Session=Depends(get_db)):
    require(role,FULL);a=db.get(DashboardSnapshot,first);b=db.get(DashboardSnapshot,second)
    if not a or not b:raise HTTPException(404,"اللقطة غير موجودة")
    return compare_snapshots(a,b)
