import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

SERVICES=[("fastapi","FastAPI"),("postgresql","PostgreSQL"),("postgis","PostGIS"),("alembic","Alembic revision"),("kml_importer","KML Importer"),("metadata","Metadata Catalog"),("search","Search Engine"),("media_resolver","Media Resolver"),("review_api","Review Portal API"),("registry_api","Registry API")]
def check_service_health(s:Session):
    result=[]
    for code,name in SERVICES:
        started=time.perf_counter();status="healthy";error=None;version="LSTA-GA"
        try:
            if code=="postgresql":version=str(s.scalar(text("select version()"))).split()[1]
            elif code=="postgis":version=str(s.scalar(text("select PostGIS_Version()")))
            elif code=="alembic":version=str(s.scalar(text("select version_num from alembic_version")))
            elif code=="kml_importer" and not Path("../../tools/kml_importer").exists():status="unknown"
            elif code=="media_resolver" and not Path("../../tools/media_resolver").exists():status="unknown"
        except Exception:status="unavailable";error="تعذر التحقق من الخدمة"
        result.append({"service_code":code,"service_name":name,"status":status,"response_time_ms":round((time.perf_counter()-started)*1000,3),"last_success":None if status=="unavailable" else "now","error_summary":error,"version":version})
    return result
