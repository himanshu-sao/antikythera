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

# --- Workflow step shape (D2) ---
# A workflow step dispatches on ``adapter`` + ``action``:
#   {step_id, name, adapter, action, config, next_step}
# ``type`` marks exactly one thing: a human-in-the-loop step (HITL_STEP_TYPE).
HITL_STEP_TYPE = "ORCHESTRATOR_TASK"
# Action given to a migrated step that has none and whose adapter is not "internal".
LEGACY_DEFAULT_ACTION = "fetch_resource"


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _legacy_action(step: Dict[str, Any], adapter: str) -> str:
    """The action a migrated step runs: its own action, else config.action for an
    internal adapter, else fetch_resource."""
    own = step.get("action")
    if isinstance(own, str) and own.strip():
        return own
    config = step.get("config")
    config_action = config.get("action") if isinstance(config, dict) else None
    if adapter.strip().lower() == "internal" and isinstance(config_action, str) and config_action.strip():
        return config_action
    return LEGACY_DEFAULT_ACTION


def migrate_step(step: Any) -> Any:
    """Return ``step`` in the adapter + action shape. Never mutates the input.

    A legacy step names its integration in ``type`` and has no adapter of its
    own (the ``adapter`` key is absent or blank): ``{"type": "github", ...}``
    becomes ``adapter="github"`` with ``type`` dropped. ``action`` is the step's
    own non-blank action, else ``config.action`` for an internal adapter, else
    ``fetch_resource``. ``config`` and the other fields are kept.

    A stored-template step with no ``type`` takes its adapter from
    ``config.adapter`` (lowercased), or defaults to ``internal`` when only
    ``config.action`` is present, matching the legacy engine's default.

    Returned unchanged (as a copy): ORCHESTRATOR_TASK steps, steps that already
    name an adapter (including an explicit null, which the validator reports),
    and steps with neither a ``type`` nor a usable ``config.adapter`` /
    ``config.action``. Non-dict entries are returned as given.
    """
    if not isinstance(step, dict):
        return step
    migrated = dict(step)
    if migrated.get("type") == HITL_STEP_TYPE:
        return migrated
    if "adapter" in migrated and not _is_blank(migrated["adapter"]):
        return migrated
    if "adapter" in migrated and migrated["adapter"] is None:
        return migrated
    step_type = migrated.get("type")
    if not (isinstance(step_type, str) and step_type.strip()):
        # Stored-template shape (pre-D2 workflow_templates.json): no top-level
        # ``type`` or ``adapter``; the adapter sits in ``config.adapter`` (for
        # example "github", "INTERNAL", "BOB_SHELL") or is implied by an
        # ``config.action`` (the old engine defaulted those to INTERNAL).
        config = migrated.get("config")
        config = config if isinstance(config, dict) else {}
        config_adapter = config.get("adapter")
        if isinstance(config_adapter, str) and config_adapter.strip():
            migrated["adapter"] = config_adapter.strip().lower()
            migrated["action"] = _legacy_action(migrated, migrated["adapter"])
            return migrated
        config_action = config.get("action")
        if isinstance(config_action, str) and config_action.strip():
            migrated["adapter"] = "internal"
            migrated["action"] = _legacy_action(migrated, "internal")
            return migrated
        return migrated
    migrated.pop("type")
    migrated["adapter"] = step_type
    migrated["action"] = _legacy_action(migrated, step_type)
    return migrated
