from typing import Literal

from pydantic import BaseModel, Field


class SpatialSearchParams(BaseModel):
    center_lat: float | None = Field(None, ge=-90, le=90)
    center_lon: float | None = Field(None, ge=-180, le=180)
    radius_meters: float | None = Field(None, gt=0, le=100_000)
    bbox: tuple[float, float, float, float] | None = None


class SearchRequest(SpatialSearchParams):
    q: str = ""
    source: Literal["registry", "staging", "all"] = "all"
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SearchResult(BaseModel):
    result_type: str
    source: Literal["registry", "staging"]
    national_id: str | None = None
    feature_id: str | None = None
    name_ar: str | None = None
    name_en: str | None = None
    normalized_name: str = ""
    description_excerpt: str = ""
    geometry_type: str
    category: str | None = None
    municipality: str | None = None
    verification_status: str
    publication_status: str | None = None
    review_status: str | None = None
    quality_score: float | None = None
    has_images: bool = False
    image_count: int = 0
    primary_image: str | None = None
    centroid: tuple[float, float] | None = None
    bbox: tuple[float, float, float, float] | None = None
    distance_meters: float | None = None
    relevance_score: float
    matched_fields: list[str] = []
    highlighted_name: str | None = None
    highlighted_description: str | None = None
    detail_url: str
    is_review_data: bool


class SearchResponse(BaseModel):
    items: list[SearchResult]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    query_time_ms: float
    applied_filters: dict[str, object] = {}


class AutocompleteResult(BaseModel):
    label: str
    secondary_label: str | None = None
    type: str
    national_id: str | None = None
    feature_id: str | None = None
    source: str
    score: float
    detail_url: str


class AutocompleteResponse(BaseModel):
    items: list[AutocompleteResult]


class SearchFacetGroup(BaseModel):
    name: str
    values: dict[str, int]


class SearchFacetsResponse(BaseModel):
    groups: list[SearchFacetGroup]


class SearchSuggestionResponse(BaseModel):
    corrected_query: str
    alternative_terms: list[str]
    likely_entities: list[AutocompleteResult]
    did_you_mean: str | None = None
