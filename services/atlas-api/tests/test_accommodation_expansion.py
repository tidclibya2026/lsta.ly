from types import SimpleNamespace

import pytest

from app.services.accommodation_expansion_selection_service import (
    calculate_expansion_safety_score,
    validate_twenty_hotel_selection,
)


def item(i):return SimpleNamespace(id=i,confidence_score=100,name_similarity=100,distance_meters=0,conflict_severity="none",excel_name="a",kml_name="a",kml_snapshot={"longitude":13,"latitude":32})
def test_exactly_twenty():assert validate_twenty_hotel_selection([item(i)for i in range(20)])
@pytest.mark.parametrize("count",[19,21])
def test_reject_wrong_count(count):
    with pytest.raises(ValueError):validate_twenty_hotel_selection([item(i)for i in range(count)])
def test_expansion_score():assert calculate_expansion_safety_score(item(1))==100
