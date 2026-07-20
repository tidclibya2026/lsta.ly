from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Operation = Literal["create_national_site","update_existing_site","keep_separate","no_operation"]
class PreviewRequest(BaseModel): proposal_id: UUID; operation_type: Operation; target_site_id: UUID|None=None
class BatchRequest(BaseModel): merge_batch_id: UUID; proposal_ids: list[UUID]=Field(min_length=1,max_length=100); operation_type: Operation="create_national_site"; requester_reference: str|None=None
class AuthorizationRequest(BaseModel): authorizer_reference: str|None=None; confirmation: str
class ExecuteRequest(BaseModel): confirmation: str; idempotency_key: str=Field(min_length=8,max_length=200)
class RollbackRequest(BaseModel): confirmation: str
