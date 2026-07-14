from typing import Optional, List
from pydantic import BaseModel, Field, field_validator
import re
from api.constants import VALID_STAGES, VALID_PRIORITIES, VALID_COMPLEXITIES

class CreateItemRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(..., min_length=1, max_length=200)
    goal: Optional[str] = Field(default=None, max_length=2000)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default="medium")
    complexity: Optional[str] = Field(default=None)
    source_type: Optional[str] = Field(default=None)
    source_value: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)
    
    @field_validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('due_date must be in YYYY-MM-DD format')
        return v

    @field_validator('item_id')
    @classmethod
    def item_id_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in VALID_PRIORITIES:
            raise ValueError(f'priority must be one of {VALID_PRIORITIES}')
        return v.lower() if v else "medium"

    @field_validator('complexity')
    @classmethod
    def validate_complexity(cls, v: Optional[str]) -> Optional[str]:
        """Accept ``None`` (default / let refiner decide), ``"auto"`` (UI
        sentinel), or one of ``VALID_COMPLEXITIES``.  Return lowercased."""
        if v is None:
            return None
        if v.lower() == "auto":
            return "auto"
        if v.lower() not in VALID_COMPLEXITIES:
            raise ValueError(f'complexity must be one of {VALID_COMPLEXITIES} or "auto"')
        return v.lower()

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory", "text"]:
            raise ValueError('source_type must be "url", "directory", or "text"')
        return v.lower() if v else None

class MoveRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50)
    new_stage: str = Field(...)
    order: Optional[int] = Field(default=None, ge=0)

    @field_validator('new_stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()

class ReorderRequest(BaseModel):
    stage: str = Field(...)
    ordered_ids: List[str] = Field(..., min_length=1)

    @field_validator('stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()

class UpdateItemRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default=None)
    complexity: Optional[str] = Field(default=None)
    confidence_score: Optional[int] = Field(default=None, ge=0, le=100)
    source_type: Optional[str] = Field(default=None)
    source_value: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None)
    blocked_reason: Optional[str] = Field(default=None)
    
    @field_validator('due_date')
    @classmethod
    def validate_due_date(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            raise ValueError('due_date must be in YYYY-MM-DD format')
        return v

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.lower() not in VALID_PRIORITIES:
            raise ValueError(f'Invalid priority. Must be one of: {VALID_PRIORITIES}')
        return v

    @field_validator('complexity')
    @classmethod
    def validate_complexity(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.lower() == "auto":
            return v
        if v.lower() not in VALID_COMPLEXITIES:
            raise ValueError(f'complexity must be one of {VALID_COMPLEXITIES} or "auto"')
        return v.lower()

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory", "text"]:
            raise ValueError('source_type must be "url", "directory", or "text"')
        return v.lower() if v else None

class CommentRequest(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=5000)
