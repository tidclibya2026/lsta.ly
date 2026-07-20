from types import SimpleNamespace

import pytest

from app.services.accommodation_pilot_selection_service import score_pilot_safety, validate_pilot_sample


def p(i):return SimpleNamespace(id=i,confidence_score=100,name_similarity=100,distance_meters=0,conflict_severity="none",excel_name="a",kml_name="a")
def test_exactly_five():assert validate_pilot_sample([p(i)for i in range(5)])
def test_reject_six():
    with pytest.raises(ValueError):validate_pilot_sample([p(i)for i in range(6)])
def test_safety_score():assert score_pilot_safety(p(1))==100
