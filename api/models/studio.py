"""
Studio Graph & Type Definitions (Slice 1 - Phase 1)

This module defines the shared type system between the interactive Studio authoring surface
and the headless PathStepGraphEngine. It is the single source of truth for node archetypes,
graph structure, skills, and execution types.

Decisions implemented (see docs/plans/mighty-greeting-cookie.md Appendix):
- dec #3: Supersedes WorkflowArchitect/BlueprintArchitect surface
- dec #5, #6: Hybrid save = durable headless template + undefined queue
- dec #8, #19: Condition-first routing with reserved signature for Phase 2 AI fallback
- dec #9, #10: Model tiers / capability declaration on graph and nodes
- dec #12: Author-time capability + suggested_model_tier emitted per proposal
- dec #13, #18: Skill = persisted AI-transform node (disk-backed)
- dec #17: Shared model defs via api.models.studio import (no shared-evaluator extraction)
- dec #20: Undefined queue cap = 100/graph, no auto-expiry
- dec #21: Replay history = 50 run logs + perpetual aggregate
- dec #22: Single shared ui/src/types/studio.ts (this file is the Python mirror)
- dec #23: Delete dead endpoints /api/automation/templates, GET /api/automation/state
- dec #28: List/vector query actions on adapters (fetch_resource returns 1, never a list)
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Primitive References (used across node types)
# -----------------------------------------------------------------------------

AdapterRef = str      # e.g., "jira_adapter", "github_adapter", "internal_adapter"
InputRef = str        # Dot-path into execution state, e.g., "jira_tickets"
OutputRef = str       # Dot-path for writing output, e.g., "extracted_fields.os_distro"
SkillRef = str        # skill_id reference to persisted Skill
LoopOverSpec = Dict[str, str]  # {"source": "jira_tickets", "iterator_var": "ticket"}


# -----------------------------------------------------------------------------
# Capability & Model Tier System (dec #9, #10)
# -----------------------------------------------------------------------------

class CapabilityTier(str, Enum):
    """
    Graph/node capability declaration — runtime resolves to provider+model via
    AI Engine config's "Model tiers" table (dec #10).
    """
    CLASSIFY = "classify"           # 4-8B local: constrained yes/no classification
    GENERATE = "generate"           # Current default: general generation
    REASON_OVER_CODE = "reason_over_code"  # 20B/27B+: complex reasoning over code


# Default tier for graphs/nodes that declare no tier (dec #10: "Default unchanged")
DEFAULT_CAPABILITY: CapabilityTier = CapabilityTier.GENERATE


# -----------------------------------------------------------------------------
# Node Archetypes (dec #0, #27, #28)
# -----------------------------------------------------------------------------

class NodeArchetype(str, Enum):
    QUERY = "query"                 # Fetch live data (list/vector) from adapter
    FAN_OUT = "fan_out"             # Loop: one branch per item (OperatorRegistry.loop_over)
    AI_TRANSFORM = "ai_transform"   # One-off script OR saved Skill (SafeExecutor mode=SCRIPT)
    CONDITIONAL_ACTION = "conditional_action"  # Condition-first routing + optional signature


class ExecutionMode(str, Enum):
    ADAPTER = "adapter"     # Native adapter call (OperatorRegistry operator_map)
    SCRIPT = "script"       # SafeExecutor Python snippet (AITransform always SCRIPT)


class RoutingStrategy(str, Enum):
    CONDITION_FIRST = "condition_first"      # Exact condition match (free)
    SIGNATURE_FALLBACK = "signature_fallback"  # Phase 2: 4-8B classifier on signature corpus


class FailureFlavor(str, Enum):
    UNDEFINED = "undefined"           # "Don't recognize, cheap to triage" (dec #11)
    ESCALATED = "escalated"           # "Recognize but can't safely complete" (dec #11)


# -----------------------------------------------------------------------------
# Condition Expression (shared with OperatorRegistry.Condition/ConditionLogic)
# -----------------------------------------------------------------------------

class ConditionType(str, Enum):
    EQUALS = "equals"
    CONTAINS = "contains"
    REGEX_MATCH = "regex_match"
    IN_LIST = "in_list"
    EXISTS = "exists"


class Condition(BaseModel):
    """Simple condition (mirrors OperatorRegistry.Condition)."""
    type: ConditionType
    field: str       # Dot-path, e.g., "extracted_fields.os_distro"
    value: Any
    case_sensitive: bool = False


class ConditionLogic(BaseModel):
    """Compound condition (AND/OR)."""
    logic: Literal["AND", "OR"]
    conditions: List[Condition]


# Discriminated union via field presence
ConditionExpr = Union[Condition, ConditionLogic]


def is_compound_condition(cond: ConditionExpr) -> bool:
    return isinstance(cond, ConditionLogic)


# -----------------------------------------------------------------------------
# Base Node (all executable nodes share these)
# -----------------------------------------------------------------------------

class BaseNode(BaseModel):
    node_id: str = Field(default_factory=lambda: f"node_{uuid4().hex[:8]}")
    archetype: NodeArchetype
    name: str
    description: Optional[str] = None

    # Capability declaration (dec #9, #12)
    required_capability: Optional[CapabilityTier] = None
    suggested_model_tier: Optional[CapabilityTier] = None  # Emitted by proposer (dec #12)

    # Reserved for Phase 2 AI routing fallback (dec #19)
    signature: Optional[str] = Field(default=None, max_length=200)  # Short NL signature

    # Visual/authoring metadata (not used by headless engine)
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0})


# -----------------------------------------------------------------------------
# Executable Node Types (discriminated union via archetype)
# -----------------------------------------------------------------------------

class QueryNode(BaseNode):
    """Fetch live data (list/vector) from an integration adapter."""
    archetype: Literal[NodeArchetype.QUERY] = NodeArchetype.QUERY
    adapter: AdapterRef
    action: str = "list_resources"  # List action on adapter (returns vector, not single)
    params: Dict[str, Any] = Field(default_factory=dict)
    output_ref: OutputRef

    # For UI: show adapter status, integration health
    adapter_status: Optional[str] = None


class FanOutNode(BaseNode):
    """Fan-out / loop: one branch per item in a list."""
    archetype: Literal[NodeArchetype.FAN_OUT] = NodeArchetype.FAN_OUT
    loop_over: LoopOverSpec  # {"source": "jira_tickets", "iterator_var": "ticket"}

    # Children are defined by graph edges from this node (source_handle = "loop")


class AITransformNode(BaseNode):
    """AI transformation: one-off script or saved Skill (dec #13, #18)."""
    archetype: Literal[NodeArchetype.AI_TRANSFORM] = NodeArchetype.AI_TRANSFORM
    execution_mode: Literal[ExecutionMode.SCRIPT] = ExecutionMode.SCRIPT  # Always SCRIPT

    # One of: inline script OR saved skill reference
    script: Optional[str] = None           # Python code for SafeExecutor
    skill_ref: Optional[SkillRef] = None   # Persisted Skill to reuse

    input_ref: InputRef
    output_ref: OutputRef

    # Model tier hint for this specific transform (dec #9)
    suggested_model_tier: Optional[CapabilityTier] = None


class ConditionalActionNode(BaseNode):
    """Condition-first routing with optional adapter actions on true/false branches."""
    archetype: Literal[NodeArchetype.CONDITIONAL_ACTION] = NodeArchetype.CONDITIONAL_ACTION
    condition: ConditionExpr
    routing_strategy: RoutingStrategy = RoutingStrategy.CONDITION_FIRST

    # True branch: adapter action to execute when condition matches
    true_action: Optional[AdapterRef] = None
    true_action_config: Dict[str, Any] = Field(default_factory=dict)
    true_output_ref: Optional[OutputRef] = None

    # False branch: optional adapter action
    false_action: Optional[AdapterRef] = None
    false_action_config: Dict[str, Any] = Field(default_factory=dict)
    false_output_ref: Optional[OutputRef] = None

    # Phase 2: NL signature for 4-8B classifier (dec #19: short labeled examples)
    signature: Optional[str] = Field(default=None, max_length=200)


# Discriminated union for all executable node types
StudioNode = Union[QueryNode, FanOutNode, AITransformNode, ConditionalActionNode]


# Type guards
def is_query_node(node: StudioNode) -> bool:
    return node.archetype == NodeArchetype.QUERY


def is_fan_out_node(node: StudioNode) -> bool:
    return node.archetype == NodeArchetype.FAN_OUT


def is_ai_transform_node(node: StudioNode) -> bool:
    return node.archetype == NodeArchetype.AI_TRANSFORM


def is_conditional_action_node(node: StudioNode) -> bool:
    return node.archetype == NodeArchetype.CONDITIONAL_ACTION


# -----------------------------------------------------------------------------
# Collapse / Pick Specification (NOT a graph node — scope narrowing, dec #0)
# -----------------------------------------------------------------------------

class CollapseSpec(BaseModel):
    type: Literal["pick_first", "pick_n", "filter"]
    n: Optional[int] = None                 # For pick_n
    filter_condition: Optional[ConditionExpr] = None  # For filter


# -----------------------------------------------------------------------------
# Graph Structure
# -----------------------------------------------------------------------------

class GraphEdge(BaseModel):
    edge_id: str = Field(default_factory=lambda: f"edge_{uuid4().hex[:8]}")
    source: str  # source node_id
    target: str  # target node_id
    source_handle: Optional[str] = None  # For FanOut: "loop" | "true" | "false"
    target_handle: Optional[str] = None  # For FanOut entry point


class StudioGraph(BaseModel):
    """
    The serializable Studio Graph — saved as durable headless template (dec #5, #6).

    Storage: automation-ideas/studio_graphs/<graph_id>.json
    Manager: StudioGraphManager (new)
    """
    graph_id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Nodes and edges
    nodes: List[StudioNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

    # Graph-level capability declaration (dec #9)
    required_capability: CapabilityTier = DEFAULT_CAPABILITY

    # Cron scheduling (dec #7) — simple graphs only in Slice 1
    cron_schedule: Optional[str] = None  # e.g., "0 9 * * 1-5"
    cron_enabled: bool = False

    # Undefined queue config (dec #20)
    undefined_queue_cap: int = 100

    # Replay history config (dec #21)
    max_run_logs: int = 50


# -----------------------------------------------------------------------------
# Execution Types (for headless PathStepGraphEngine)
# -----------------------------------------------------------------------------

class ExecutionState(BaseModel):
    """Mutable execution state during a graph run."""
    graph_id: str
    run_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    current_node_id: Optional[str] = None
    state: Dict[str, Any] = Field(default_factory=dict)  # All node outputs keyed by output_ref
    loop_stack: List[Dict[str, Any]] = Field(default_factory=list)  # For nested fan-out
    undefined_queue: List[Dict[str, Any]] = Field(default_factory=list)
    run_log: List[Dict[str, Any]] = Field(default_factory=list)
    # dec #16 dry-run mode: when True, the conditional true/false branches that
    # would normally fire a live adapter write (update_resource) are short-
    # circuited to a logged "would-have-run" result. Reads (Query list/vector)
    # still execute so routing/queue/condition-match can be verified without
    # side effects. Lets a graph be exercised end-to-end before the single
    # real Jira write at slice-1 end (plan §6, "after dry-run logging").
    dry_run: bool = False


class NodeExecutionResult(BaseModel):
    """Result of executing a single node."""
    node_id: str
    status: Literal["success", "skipped", "failed", "undefined", "escalated"]
    output: Optional[Any] = None
    error: Optional[str] = None
    failure_flavor: Optional[FailureFlavor] = None
    execution_time_ms: int = 0
    matched_branch: Optional[Literal["true", "false"]] = None  # For ConditionalAction


class GraphRunLog(BaseModel):
    """Persisted run log (dec #21: last 50 + perpetual aggregate)."""
    run_id: str
    graph_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: Literal["running", "completed", "failed", "partial"]
    node_results: List[NodeExecutionResult] = Field(default_factory=list)
    undefined_items: List[Dict[str, Any]] = Field(default_factory=list)
    escalated_items: List[Dict[str, Any]] = Field(default_factory=list)

    # Aggregate counters for perpetual dashboard
    total_matched: int = 0
    total_undefined: int = 0
    total_escalated: int = 0


# -----------------------------------------------------------------------------
# Skill Persistence (dec #13, #18)
# -----------------------------------------------------------------------------

class Skill(BaseModel):
    """Persisted reusable AI Transform (dec #13: migrated from in-memory dict to disk)."""
    skill_id: str
    name: str
    description: str
    script: str  # Python code for SafeExecutor
    input_schema: Dict[str, Any] = Field(default_factory=dict)  # JSON schema for input_ref
    output_schema: Dict[str, Any] = Field(default_factory=dict)  # JSON schema for output_ref
    version: str = "1.0.0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)

    # Capability tier this skill requires (dec #9)
    required_capability: CapabilityTier = DEFAULT_CAPABILITY


# -----------------------------------------------------------------------------
# Storage Paths & Constants
# -----------------------------------------------------------------------------

STUDIO_GRAPHS_DIR = "studio_graphs"
SKILLS_DIR = "skills"
STUDIO_RUNS_DIR = "studio_runs"

# SEC-11: graph and skill ids become file names under the studio dirs, so they
# must never contain path separators, dots or other unsafe characters.
SAFE_STUDIO_ID_PATTERN = r"^[A-Za-z0-9_-]{1,100}$"
_SAFE_STUDIO_ID_RE = re.compile(SAFE_STUDIO_ID_PATTERN)


def is_safe_studio_id(value: Any) -> bool:
    """True when ``value`` is a string id safe to use as a file name stem."""
    return isinstance(value, str) and _SAFE_STUDIO_ID_RE.fullmatch(value) is not None


# -----------------------------------------------------------------------------
# Graph shape validation (S6 / P2-10)
# -----------------------------------------------------------------------------

def validate_graph_shape(nodes: List[Any], edges: List[Any]) -> List[str]:
    """Return human-readable problems with a graph's shape (empty list = valid).

    Checks, in order:
    - duplicate node ids;
    - edges whose source or target is not a node of the graph;
    - cycles. Loop edges (``source_handle == "loop"``) count as ordinary edges
      here, so a loop edge pointing back at its own FanOut ancestor chain is a
      cycle too. Uses Kahn's algorithm; the nodes left over are on a cycle.

    ``nodes`` / ``edges`` may be models or plain dicts.
    """

    def _get(obj: Any, key: str) -> Any:
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    problems: List[str] = []

    seen: Dict[str, int] = {}
    for node in nodes:
        nid = _get(node, "node_id")
        seen[nid] = seen.get(nid, 0) + 1
    for nid, count in seen.items():
        if count > 1:
            problems.append(f"Duplicate node id '{nid}' ({count} nodes share it)")

    node_ids = set(seen)
    valid_edges = []
    for edge in edges:
        src, dst = _get(edge, "source"), _get(edge, "target")
        missing = [
            f"{label} '{value}'"
            for label, value in (("source", src), ("target", dst))
            if value not in node_ids
        ]
        if missing:
            problems.append(
                f"Edge {src!r} -> {dst!r} references a node that does not exist: " + ", ".join(missing)
            )
        else:
            valid_edges.append((src, dst))

    indegree: Dict[str, int] = {nid: 0 for nid in node_ids}
    successors: Dict[str, List[str]] = {nid: [] for nid in node_ids}
    for src, dst in valid_edges:
        successors[src].append(dst)
        indegree[dst] += 1
    queue = [nid for nid, deg in indegree.items() if deg == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for nxt in successors[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    if visited < len(node_ids):
        cyclic = sorted(nid for nid, deg in indegree.items() if deg > 0)
        problems.append("Graph contains a cycle involving: " + ", ".join(str(n) for n in cyclic))

    return problems


# -----------------------------------------------------------------------------
# Corrupt on-disk file handling (R8 / P0-5)
# -----------------------------------------------------------------------------

class CorruptStudioFileError(RuntimeError):
    """A graph or skill file exists but is not a readable JSON object.

    The message carries no filesystem path (only the id and the backup file's
    name). The unreadable file is copied to ``<file>.corrupt-<UTC>`` by the
    manager and the original is left in place, so a later create with the same
    id cannot silently overwrite it.
    """

    def __init__(self, kind: str, item_id: str, backup_name: Optional[str] = None):
        self.kind = kind
        self.item_id = item_id
        self.backup_name = backup_name
        detail = f" A copy was saved as '{backup_name}'." if backup_name else ""
        super().__init__(
            f"The stored {kind} '{item_id}' is corrupt and cannot be read.{detail} "
            f"The original file was left untouched; restore or remove it before retrying."
        )


def load_studio_json_object(path: str, kind: str, item_id: str) -> Optional[Dict[str, Any]]:
    """Read ``path`` as a JSON object. Missing file -> None.

    Invalid JSON, bad UTF-8, a non-object root or an unreadable file raise
    :class:`CorruptStudioFileError`. Unparseable content is quarantined the same
    way ``api/managers/base.py`` does it (copy to ``<file>.corrupt-<UTC>``,
    identical backups reused, original left in place).
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError
        raise CorruptStudioFileError(kind, item_id, _quarantine_studio_file(path, exc)) from exc
    except OSError as exc:
        raise CorruptStudioFileError(kind, item_id) from exc
    if not isinstance(data, dict):
        exc = ValueError(f"root is {type(data).__name__}, expected a JSON object")
        raise CorruptStudioFileError(kind, item_id, _quarantine_studio_file(path, exc))
    return data


def _quarantine_studio_file(path: str, exc: Exception) -> Optional[str]:
    """Back up an unreadable file via BaseJSONManager._quarantine; return the backup's file name.

    Imported lazily to avoid a models -> managers import cycle.
    """
    from api.managers.base import BaseJSONManager

    try:
        helper = BaseJSONManager(os.path.dirname(path), os.path.basename(path))
        return os.path.basename(helper._quarantine(exc).backup_path)
    except Exception:  # backup is best effort; the original is never touched
        return None
