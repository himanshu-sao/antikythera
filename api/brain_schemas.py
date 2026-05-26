from typing import Optional, Literal, Any, Dict
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class ObserverEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: Literal["RUN_STARTED", "STEP_START", "STEP_END", "RUN_COMPLETED", "KANBAN_TRANSITION", "USER_INTERVENTION", "TOOL_ERROR", "TASK_SUCCESS", "ARTIFACT_COMMENT", "ERROR"] = Field(...)
    event_data: Dict[str, Any] = Field(..., description="Detailed data related to the event (e.g., task_id, user_comment, error_msg)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CognitiveDelta(BaseModel):
    delta_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    target_artifact: Literal["user.md", "skills.md", "memory.md"] = Field(...)
    change_type: Literal["ADD", "REMOVE", "REPLACE", "REVISE"] = Field(...)
    original_content: Optional[str] = Field(None, description="The text being replaced or removed")
    proposed_content: str = Field(..., description="The new proposed text")
    reason: str = Field(..., description="The observation/justification for this delta")
    source_event_id: Optional[str] = Field(None, description="Reference to the ObserverEvent that triggered this")
    status: Literal["PENDING", "APPROVED", "REJECTED", "REFINED"] = Field(default="PENDING")
    confidence_score: int = Field(default=50, ge=0, le=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    refined_by_comment: Optional[str] = Field(None, description="The user comment that led to a REFINED status")

class BrainStateRequest(BaseModel):
    """Request to fetch the current state of the brain artifacts."""
    artifacts: Dict[str, str] = Field(..., description="Mapping of filename to its current content")

class BrainUpdateResponse(BaseModel):
    """Response after an approved delta is committed."""
    success: bool
    applied_delta_id: str
    message: str
