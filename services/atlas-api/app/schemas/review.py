from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ReviewDecisionRequest(BaseModel):
    review_stage: Literal["technical", "gis", "data", "final"]
    decision: Literal["pending", "accepted", "rejected", "needs_correction"]
    reviewer_id: uuid.UUID | None = None
    reviewer_role: str = Field(min_length=2, max_length=120)
    notes: str | None = None
    proposed_name_ar: str | None = None
    proposed_category_id: uuid.UUID | None = None
    proposed_municipality_id: uuid.UUID | None = None


class PromoteRequest(BaseModel):
    promoted_by: uuid.UUID | None = None


class BulkPromotePreviewRequest(BaseModel):
    feature_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
