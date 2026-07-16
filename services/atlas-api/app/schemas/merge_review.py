from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

MergeDecisionValue = Literal["approved_merge","rejected_match","needs_field_verification","create_from_excel","create_from_kml","keep_separate","duplicate_excel","duplicate_kml","deferred"]
class MergeBatchSummary(BaseModel):id:UUID;batch_code:str;entity_type:str;proposal_count:int;status:str
class MergeBatchDetail(MergeBatchSummary):excel_file_name:str;kml_file_name:str;excel_record_count:int;kml_record_count:int;raw_candidate_count:int;engine_version:str;matching_parameters:dict[str,Any]
class MergeProposalListItem(BaseModel):id:UUID;batch_id:UUID;excel_record_id:str;kml_record_id:str;excel_name:str|None;kml_name:str|None;confidence_score:float;name_similarity:float;distance_meters:float|None;candidate_class:str;conflict_severity:str;review_status:str;priority:str;assigned_role:str|None
class MergeDecisionHistoryItem(BaseModel):id:UUID;decision:str;review_stage:str;reviewer_role:str;decision_reason:str|None;reviewer_notes:str|None;decided_at:Any
class MergeProposalDetail(MergeProposalListItem):conflict_fields:list[Any];excel_snapshot:dict[str,Any];kml_snapshot:dict[str,Any];proposed_site:dict[str,Any];field_sources:dict[str,Any];history:list[MergeDecisionHistoryItem]=[]
class MergeComparison(BaseModel):proposal_id:UUID;excel:dict[str,Any];kml:dict[str,Any];proposed_site:dict[str,Any];field_sources:dict[str,Any];score:dict[str,Any];conflicts:list[Any]
class MergeDecisionRequest(BaseModel):decision:MergeDecisionValue;decision_reason:str|None=None;reviewer_notes:str|None=None;review_stage:str="merge_review";decision_metadata:dict[str,Any]=Field(default_factory=dict)
class MergeDecisionResponse(BaseModel):proposal_id:UUID;decision_id:UUID;review_status:str;automatic_merge:bool=False;promotion_created:bool=False
class MergeReviewProgress(BaseModel):total:int;reviewed:int;pending:int;percentage:float
class MergeSummaryResponse(BaseModel):batches:int;proposals:int;pending_review:int;ready_merge:int;needs_review:int;possible_match:int;high_conflicts:int;medium_conflicts:int;approved_merge:int;rejected_match:int;progress:MergeReviewProgress
class BulkDecisionPreviewRequest(BaseModel):proposal_ids:list[UUID]=Field(min_length=1,max_length=100);decision:MergeDecisionValue
class BulkDecisionPreviewResponse(BaseModel):eligible_ids:list[UUID];rejected:dict[str,str];preview_token:str;writes:int=0
class BulkDecisionRequest(BulkDecisionPreviewRequest):preview_token:str;decision_reason:str|None=None;reviewer_notes:str|None=None
class BulkDecisionResponse(BaseModel):decisions_created:int;proposal_ids:list[UUID];automatic_merge:bool=False
class UnmatchedSummary(BaseModel):unmatched_excel_records:int;unmatched_kml_records:int
