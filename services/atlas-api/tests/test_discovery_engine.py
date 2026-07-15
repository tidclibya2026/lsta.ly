from app.services.arabic_text_service import (
    detect_query_language,
    generate_search_variants,
    normalize_arabic_text,
    tokenize_mixed_query,
)
from app.services.duplicate_detection_service import calculate_duplicate_confidence
from app.services.search_ranking_service import calculate_ranking


def test_real_arabic_normalization_and_mixed_query() -> None:
    assert normalize_arabic_text("  المَدِينَةُ القَدِيمَة  ") == "المدينه القديمه"
    assert normalize_arabic_text("المدينه القديمه") == normalize_arabic_text("المدينة القديمة")
    assert detect_query_language("Tripoli طرابلس") == "mixed"
    assert tokenize_mixed_query("Tripoli طرابلس") == ["tripoli", "طرابلس"]
    assert "المدينه القديمه" in generate_search_variants("المدينة القديمة")


def test_ranking_contract_and_staging_penalty() -> None:
    registry = calculate_ranking(
        {"national_id": "LSTA-OLD-TRIPOLI-000001", "source": "registry"},
        "LSTA-OLD-TRIPOLI-000001",
        development=True,
    )
    staging = calculate_ranking(
        {"name_ar": "المدينة القديمة", "source": "staging", "review_status": "pending_review"},
        "المدينة القديمة",
    )
    assert registry["relevance_score"] == 100
    assert registry["matched_fields"] == ["national_id"]
    assert registry["ranking_reason"]
    assert staging["relevance_score"] == 87


def test_duplicate_confidence_weights() -> None:
    assert calculate_duplicate_confidence(
        name_similarity=100,
        spatial_distance_meters=0,
        description_similarity=100,
        category_match=True,
        municipality_match=True,
    ) == 100
