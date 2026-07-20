from uuid import uuid4

from app.models import Site


def build_site(**values):return Site(id=values.pop("id",uuid4()),national_id=values.pop("national_id",f"LSTA-TEST-{uuid4().hex[:12]}"),name_ar=values.pop("name_ar","موقع اختبار"),verification_status=values.pop("verification_status","draft"),**values)
