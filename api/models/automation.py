from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
from datetime import datetime

class SkillCategory(str, Enum):
    EXTRACTION = "EXTRACTION"
    TRANSFORMATION = "TRANSFORMATION"
    CLASSIFICATION = "CLASSIFICATION"
    PARSING = "PARSING"  # New: For parsing skills

class Skill(BaseModel):
    skill_id: str
    name: str
    category: SkillCategory
    few_shot_prompt: str
    output_schema: Dict[str, Any]
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    skill_type: Literal["action", "parse"] = "action"  # New: Distinguish action vs parse skills
    parser_config: Optional[Dict[str, Any]] = None  # New: Regex patterns for parsing

# --- Condition Models ---
class ConditionType(str, Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    REGEX_MATCH = "regex_match"
    IN_LIST = "in_list"
    EXISTS = "exists"

class Condition(BaseModel):
    type: ConditionType
    field: str  # e.g., "extracted_fields.os_distro"
    value: Any
    case_sensitive: bool = False

class ConditionLogic(BaseModel):
    logic: Literal["AND", "OR"]
    conditions: List[Condition]

# --- Extended PathStep Model ---
class ExecutionMode(str, Enum):
    ADAPTER = "adapter"  # Default: Use existing adapter logic
    SCRIPT = "script"    # New: Run AI-generated Python code

class PathStep(BaseModel):
    step_id: str
    operator_id: str
    adapter_id: str
    config: Dict[str, Any]
    input_ref: Optional[str] = None
    output_ref: Optional[str] = None
    
    # --- NEW FIELDS FOR PHASE 1.5 ---
    mode: ExecutionMode = ExecutionMode.ADAPTER  # Default: Backward compatible
    condition: Optional[Dict[str, Any]] = None   # ConditionDict or ConditionLogic (JSON)
    loop_over: Optional[Dict[str, str]] = None   # {"source": "jira_tickets", "iterator_var": "ticket"}

# --- Path Model (No changes needed) ---
class Path(BaseModel):
    path_id: str
    pipeline_id: str
    name: str
    steps: List[PathStep] = []
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

# --- Trigger & Pipeline Models (No major changes) ---
class TriggerType(str, Enum):
    CRON = "CRON"
    WEBHOOK = "WEBHOOK"
    MANUAL = "MANUAL"

class Pipeline(BaseModel):
    pipeline_id: str
    name: str
    description: Optional[str] = None
    paths: List[str] = []
    trigger: Dict[str, Any]
    global_context: Dict[str, str] = {}
    status: str = "DRAFT"
    created_at: datetime = Field(default_factory=datetime.utcnow)

# --- Execution Log (Child Runs & Audit) ---
class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # New: For conditional skips
    AUTH_REQUIRED = "auth_required"  # New: For authentication required

class ExecutionLog(BaseModel):
    run_id: Optional[str] = None  # Made optional for sandbox execution
    pipeline_id: Optional[str] = None  # Made optional for sandbox execution
    step_id: str
    parent_run_id: Optional[str] = None  # New: For loop children
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    # --- NEW FIELDS FOR PHASE 1.5 ---
    execution_reason: Optional[str] = None  # Why skipped/failed
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)  # Structured data (Image, OS, etc.)
    result_data: Optional[Any] = None
    error_detail: Optional[str] = None
    duration_ms: Optional[int] = None

class PipelineRun(BaseModel):
    run_id: str
    pipeline_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: str  # SUCCESS, FAILED, RUNNING
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    logs: List[ExecutionLog] = []  # Updated to use new ExecutionLog model