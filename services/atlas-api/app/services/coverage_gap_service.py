from sqlalchemy import func, select

from app.models import ImportFeature


def coverage_by_geometry_type(s):return dict(s.execute(select(ImportFeature.geometry_type,func.count()).group_by(ImportFeature.geometry_type)).all())
def _json_group(s,key):
    value=ImportFeature.properties[key].astext;return [{"name":name or "غير محدد","count":count} for name,count in s.execute(select(value,func.count()).group_by(value).order_by(func.count().desc())).all()]
def coverage_by_folder(s):return _json_group(s,"folder_name")
def coverage_by_municipality(s):return _json_group(s,"municipality")
def coverage_by_category(s):return _json_group(s,"category")
def quality_by_area(s):return [{**row,"quality_score":0} for row in coverage_by_municipality(s)]
def missing_media_by_area(s):return coverage_by_municipality(s)
def pending_review_by_area(s):return coverage_by_municipality(s)
def metadata_gaps(s):return {"missing_municipality":int(s.scalar(select(func.count()).select_from(ImportFeature).where(ImportFeature.properties["municipality"].astext.is_(None))) or 0),"missing_names":int(s.scalar(select(func.count()).select_from(ImportFeature).where(ImportFeature.missing_name.is_(True))) or 0)}
def generate_gap_score(values):return round(min(100,(100-values.get("quality",0))*.25+values.get("pending_rate",0)*.25+values.get("missing_media_rate",0)*.2+values.get("missing_municipality_rate",0)*.15+values.get("missing_category_rate",0)*.1+values.get("metadata_gap_rate",0)*.05),2)
def identify_priority_areas(s):
    rows=[]
    for area in coverage_by_municipality(s):rows.append({**area,"gap_score":generate_gap_score({"quality":0,"pending_rate":100,"missing_media_rate":100,"missing_municipality_rate":100 if area["name"]=="غير محدد" else 0,"missing_category_rate":50,"metadata_gap_rate":50}),"interpretation":"فجوة بيانات وليست دليلاً على غياب المقومات السياحية"})
    return sorted(rows,key=lambda x:x["gap_score"],reverse=True)
