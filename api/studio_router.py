"""
Studio Router — REST endpoints for the Automation Studio redesign.

Endpoints:
- POST   /api/studio/graphs              - Create a new studio graph
- GET    /api/studio/graphs              - List all studio graphs
- GET    /api/studio/graphs/{graph_id}   - Get a specific graph
- PUT    /api/studio/graphs/{graph_id}   - Update a graph
- DELETE /api/studio/graphs/{graph_id}   - Delete a graph
- POST   /api/studio/graphs/{graph_id}/run - Execute a graph (returns run_id)
- GET    /api/studio/graphs/{graph_id}/runs - List run logs (last 50)
- GET    /api/studio/graphs/{graph_id}/undefined-queue - Get undefined queue (cap 100)
- GET    /api/studio/schedulable-graphs   - List graphs eligible for cron
- POST   /api/studio/skills              - Create a new skill
- GET    /api/studio/skills              - List all skills
- GET    /api/studio/skills/{skill_id}   - Get a specific skill
- DELETE /api/studio/skills/{skill_id}   - Delete a skill
- GET    /api/studio/integrations/status - Get integration connection status
"""

import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from api.managers.studio_graph_manager import StudioGraphManager
from api.managers.skill_manager import SkillManager
from api.execution.studio_graph_engine import PathStepGraphEngine
from api.workflow_state_manager import WorkflowStateManager
from api.models.studio import (
    StudioGraph,
    StudioNode,
    GraphRunLog,
    NodeExecutionResult,
    CapabilityTier,
    NodeArchetype,
    Skill,
)

router = APIRouter(prefix="/api/studio", tags=["Automation Studio"])


# -----------------------------------------------------------------------------
# Dependency Injection
# -----------------------------------------------------------------------------

def _get_base_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))


def get_studio_graph_manager() -> StudioGraphManager:
    return StudioGraphManager(_get_base_dir())


def get_skill_manager() -> SkillManager:
    return SkillManager(_get_base_dir())


def get_graph_engine(request: Request) -> PathStepGraphEngine:
    # Access from app.state (initialized in main.py lifespan)
    state_manager: WorkflowStateManager = request.app.state.state_manager
    hub = request.app.state.hub
    operator_registry = request.app.state.engine.operator_registry if hasattr(request.app.state.engine, 'operator_registry') else None

    # We need to create the engine with proper dependencies
    # For now, create inline; in production this would be in app.state
    studio_graph_manager = get_studio_graph_manager()
    skill_manager = get_skill_manager()
    run_manager = state_manager.runs

    # Import here to avoid circular
    from api.operator_registry import OperatorRegistry
    op_registry = operator_registry or OperatorRegistry(vault=None, skill_store={})

    return PathStepGraphEngine(
        base_dir=_get_base_dir(),
        operator_registry=op_registry,
        studio_graph_manager=studio_graph_manager,
        skill_manager=skill_manager,
        run_manager=run_manager,
    )


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class GraphCreateRequest(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list)
    required_capability: CapabilityTier = CapabilityTier.GENERATE
    cron_schedule: Optional[str] = None
    cron_enabled: bool = False
    undefined_queue_cap: int = 100
    max_run_logs: int = 50


class GraphUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    required_capability: Optional[CapabilityTier] = None
    cron_schedule: Optional[str] = None
    cron_enabled: Optional[bool] = None
    undefined_queue_cap: Optional[int] = None
    max_run_logs: Optional[int] = None


class GraphResponse(BaseModel):
    graph_id: str
    name: str
    description: str
    version: str
    created_at: str
    updated_at: str
    required_capability: str
    cron_schedule: Optional[str]
    cron_enabled: bool
    undefined_queue_cap: int
    max_run_logs: int
    node_count: int
    edge_count: int


class GraphDetailResponse(GraphResponse):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class RunRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    # dec #16: dry_run=True exercises the graph end-to-end (reads run, condition
    # routing + undefined-queue + run-logs all populate) but short-circuits the
    # conditional true/false adapter writes to a logged "would-have-run" result,
    # so the verification pass never fires a live Jira write. Flip False for
    # the single real write at slice-1 end (plan §6 "after dry-run logging").
    dry_run: bool = False


class RunResponse(BaseModel):
    run_id: str
    graph_id: str
    status: str
    started_at: str
    dry_run: bool = False


class RunLogResponse(BaseModel):
    run_id: str
    graph_id: str
    started_at: str
    ended_at: Optional[str]
    status: str
    node_results: List[Dict[str, Any]]
    undefined_items: List[Dict[str, Any]]
    escalated_items: List[Dict[str, Any]]
    total_matched: int
    total_undefined: int
    total_escalated: int


class UndefinedQueueResponse(BaseModel):
    graph_id: str
    items: List[Dict[str, Any]]
    cap: int


class PreviewNodeRequest(BaseModel):
    """One draft node + the in-progress execution state to preview against."""
    # A single StudioNode (validated as a discriminated union server-side).
    node: Dict[str, Any] = Field(..., description="Draft StudioNode to execute")
    # Caller-supplied execution state (outputs keyed by output_ref).
    execution_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="In-progress execution state (output_ref -> value)",
    )


class PreviewNodeResponse(BaseModel):
    """Result of a synchronous preview of a single draft node."""
    result: Optional[Any] = None
    updated_state: Dict[str, Any]
    status: str  # success | failed | undefined | skipped
    error: Optional[str] = None
    matched_branch: Optional[str] = None  # "true" | "false" for ConditionalAction


class SkillCreateRequest(BaseModel):
    skill_id: str
    name: str
    description: str
    script: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    version: str = "1.0.0"
    tags: List[str] = Field(default_factory=list)
    required_capability: CapabilityTier = CapabilityTier.GENERATE


class SkillResponse(BaseModel):
    skill_id: str
    name: str
    description: str
    version: str
    created_at: str
    updated_at: str
    tags: List[str]
    required_capability: str


class SkillDetailResponse(SkillResponse):
    script: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


# -----------------------------------------------------------------------------
# Graph Endpoints
# -----------------------------------------------------------------------------

@router.post("/graphs", response_model=GraphResponse, status_code=201)
async def create_graph(
    request: GraphCreateRequest,
    manager: StudioGraphManager = Depends(get_studio_graph_manager),
):
    """Create a new Studio Graph."""
    graph_id = f"graph_{request.name.lower().replace(' ', '_').replace('-', '_')}"

    # Check for collision
    existing = manager.get_graph(graph_id)
    if existing:
        graph_id = f"{graph_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Convert nodes/edges to models
    nodes = [StudioNode.model_validate(n) for n in request.nodes]
    edges = [GraphEdge.model_validate(e) for e in request.edges]

    graph = StudioGraph(
        graph_id=graph_id,
        name=request.name,
        description=request.description,
        version=request.version,
        nodes=nodes,
        edges=edges,
        required_capability=request.required_capability,
        cron_schedule=request.cron_schedule,
        cron_enabled=request.cron_enabled,
        undefined_queue_cap=request.undefined_queue_cap,
        max_run_logs=request.max_run_logs,
    )

    if not manager.save_graph(graph):
        raise HTTPException(status_code=500, detail="Failed to save graph")

    return _graph_to_response(graph)


@router.get("/graphs", response_model=List[GraphResponse])
async def list_graphs(manager: StudioGraphManager = Depends(get_studio_graph_manager)):
    """List all Studio Graphs (metadata only)."""
    graphs = manager.list_graphs()
    return [_graph_meta_to_response(g) for g in graphs]


@router.get("/graphs/{graph_id}", response_model=GraphDetailResponse)
async def get_graph(
    graph_id: str,
    manager: StudioGraphManager = Depends(get_studio_graph_manager),
):
    """Get a Studio Graph by ID (full detail)."""
    graph = manager.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")
    return _graph_to_detail_response(graph)


@router.put("/graphs/{graph_id}", response_model=GraphResponse)
async def update_graph(
    graph_id: str,
    request: GraphUpdateRequest,
    manager: StudioGraphManager = Depends(get_studio_graph_manager),
):
    """Update a Studio Graph."""
    graph = manager.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    # Apply updates
    if request.name is not None:
        graph.name = request.name
    if request.description is not None:
        graph.description = request.description
    if request.version is not None:
        graph.version = request.version
    if request.nodes is not None:
        graph.nodes = [StudioNode.model_validate(n) for n in request.nodes]
    if request.edges is not None:
        graph.edges = [GraphEdge.model_validate(e) for e in request.edges]
    if request.required_capability is not None:
        graph.required_capability = request.required_capability
    if request.cron_schedule is not None:
        graph.cron_schedule = request.cron_schedule
    if request.cron_enabled is not None:
        graph.cron_enabled = request.cron_enabled
    if request.undefined_queue_cap is not None:
        graph.undefined_queue_cap = request.undefined_queue_cap
    if request.max_run_logs is not None:
        graph.max_run_logs = request.max_run_logs

    graph.updated_at = datetime.utcnow()

    if not manager.save_graph(graph):
        raise HTTPException(status_code=500, detail="Failed to save graph")

    return _graph_to_response(graph)


@router.delete("/graphs/{graph_id}", status_code=204)
async def delete_graph(
    graph_id: str,
    manager: StudioGraphManager = Depends(get_studio_graph_manager),
):
    """Delete a Studio Graph."""
    if not manager.delete_graph(graph_id):
        raise HTTPException(status_code=404, detail="Graph not found")


@router.post("/graphs/{graph_id}/run", response_model=RunResponse)
async def run_graph(
    graph_id: str,
    request: RunRequest,
    engine: PathStepGraphEngine = Depends(get_graph_engine),
):
    """Execute a Studio Graph (starts async, returns run_id)."""
    manager = get_studio_graph_manager()
    graph = manager.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    run_id = engine.start_run(graph_id, request.inputs, dry_run=request.dry_run)
    run_log = engine.get_run_log(run_id)

    return RunResponse(
        run_id=run_id,
        graph_id=graph_id,
        status="running",
        started_at=run_log.started_at.isoformat() + "Z" if run_log else datetime.utcnow().isoformat() + "Z",
        dry_run=request.dry_run,
    )


@router.post("/preview-node", response_model=PreviewNodeResponse)
async def preview_node(
    request: PreviewNodeRequest,
    engine: PathStepGraphEngine = Depends(get_graph_engine),
):
    """
    Preview-execute a single draft node synchronously against the in-progress
    execution_state (Slice 1 authoring loop — the live-results-led compiler).

    The node dict is validated through the StudioNode discriminated union first,
    so a malformed draft returns 422 rather than a cryptic engine error. The
    engine reuses the same per-node handlers as headless execution (dec #17),
    so preview semantics match a real run. No run log is persisted.
    """
    try:
        # StudioNode is a discriminated Union, not a class with .model_validate —
        # use TypeAdapter so the archetype discriminator routes to the right
        # concrete node (QueryNode / FanOutNode / AITransformNode /
        # ConditionalActionNode). A bare model_validate would always raise
        # AttributeError on the Union.
        node = TypeAdapter(StudioNode).validate_python(request.node)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Invalid StudioNode: {e}")

    out = await engine.preview_node(node, request.execution_state)
    return PreviewNodeResponse(
        result=out["result"],
        updated_state=out["updated_state"],
        status=out["status"],
        error=out["error"],
        matched_branch=out["matched_branch"],
    )


@router.get("/graphs/{graph_id}/runs", response_model=List[RunLogResponse])
async def list_run_logs(
    graph_id: str,
    limit: int = 50,
    engine: PathStepGraphEngine = Depends(get_graph_engine),
):
    """List recent run logs for a graph (dec #21: last 50)."""
    logs = engine.list_run_logs(graph_id, limit=limit)
    return [
        RunLogResponse(
            run_id=log.run_id,
            graph_id=log.graph_id,
            started_at=log.started_at.isoformat() + "Z",
            ended_at=log.ended_at.isoformat() + "Z" if log.ended_at else None,
            status=log.status,
            node_results=[nr.model_dump(mode="json") for nr in log.node_results],
            undefined_items=log.undefined_items,
            escalated_items=log.escalated_items,
            total_matched=log.total_matched,
            total_undefined=log.total_undefined,
            total_escalated=log.total_escalated,
        )
        for log in logs
    ]


@router.get("/graphs/{graph_id}/undefined-queue", response_model=UndefinedQueueResponse)
async def get_undefined_queue(
    graph_id: str,
    engine: PathStepGraphEngine = Depends(get_graph_engine),
):
    """Get undefined queue items for a graph (cap 100, no auto-expiry, dec #20)."""
    manager = get_studio_graph_manager()
    graph = manager.get_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Graph not found")

    items = engine.get_undefined_queue(graph_id)
    return UndefinedQueueResponse(
        graph_id=graph_id,
        items=items,
        cap=graph.undefined_queue_cap,
    )


@router.get("/schedulable-graphs", response_model=List[GraphResponse])
async def list_schedulable_graphs(
    engine: PathStepGraphEngine = Depends(get_graph_engine),
):
    """List graphs eligible for cron execution (simple graphs only, dec #9)."""
    graphs = engine.get_schedulable_graphs()
    return [_graph_to_response(g) for g in graphs]


# -----------------------------------------------------------------------------
# Skill Endpoints (dec #13, #18)
# -----------------------------------------------------------------------------

@router.post("/skills", response_model=SkillResponse, status_code=201)
async def create_skill(
    request: SkillCreateRequest,
    manager: SkillManager = Depends(get_skill_manager),
):
    """Create a new persisted Skill (disk-backed, dec #13)."""
    skill = Skill(
        skill_id=request.skill_id,
        name=request.name,
        description=request.description,
        script=request.script,
        input_schema=request.input_schema,
        output_schema=request.output_schema,
        version=request.version,
        tags=request.tags,
        required_capability=request.required_capability,
    )

    if not manager.save_skill(skill):
        raise HTTPException(status_code=500, detail="Failed to save skill")

    return _skill_to_response(skill)


@router.get("/skills", response_model=List[SkillResponse])
async def list_skills(manager: SkillManager = Depends(get_skill_manager)):
    """List all persisted Skills."""
    skills = manager.list_skills()
    return [_skill_meta_to_response(s) for s in skills]


@router.get("/skills/{skill_id}", response_model=SkillDetailResponse)
async def get_skill(
    skill_id: str,
    manager: SkillManager = Depends(get_skill_manager),
):
    """Get a Skill by ID (full detail)."""
    skill = manager.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _skill_to_detail_response(skill)


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    manager: SkillManager = Depends(get_skill_manager),
):
    """Delete a Skill."""
    if not manager.delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")


# -----------------------------------------------------------------------------
# Integration Status (dec #14: env var credentials, show status + link to Integrations Hub)
# -----------------------------------------------------------------------------

@router.get("/integrations/status")
async def get_integration_status():
    """Get integration connection status for Studio UI."""
    config_path = os.path.join(_get_base_dir(), "integrations.json")

    if not os.path.exists(config_path):
        return {"integrations": []}

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except Exception:
        config = {}

    integrations = []
    for name, data in config.items():
        integrations.append({
            "name": name,
            "type": data.get("type", "native"),
            "adapter_module": data.get("config", {}).get("adapter_module"),
            "status": data.get("status", "disconnected"),
            "connected": data.get("status") == "connected",
        })

    return {"integrations": integrations}


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _graph_to_response(graph: StudioGraph) -> GraphResponse:
    return GraphResponse(
        graph_id=graph.graph_id,
        name=graph.name,
        description=graph.description,
        version=graph.version,
        created_at=graph.created_at.isoformat() + "Z",
        updated_at=graph.updated_at.isoformat() + "Z",
        required_capability=graph.required_capability.value,
        cron_schedule=graph.cron_schedule,
        cron_enabled=graph.cron_enabled,
        undefined_queue_cap=graph.undefined_queue_cap,
        max_run_logs=graph.max_run_logs,
        node_count=len(graph.nodes),
        edge_count=len(graph.edges),
    )


def _graph_to_detail_response(graph: StudioGraph) -> GraphDetailResponse:
    base = _graph_to_response(graph)
    return GraphDetailResponse(
        **base.model_dump(),
        nodes=[n.model_dump(mode="json") for n in graph.nodes],
        edges=[e.model_dump(mode="json") for e in graph.edges],
    )


def _graph_meta_to_response(meta: Dict[str, Any]) -> GraphResponse:
    return GraphResponse(
        graph_id=meta["graph_id"],
        name=meta["name"],
        description=meta.get("description", ""),
        version=meta.get("version", "1.0.0"),
        created_at=meta.get("created_at", "") or "",
        updated_at=meta.get("updated_at", "") or "",
        required_capability=meta.get("required_capability", "generate"),
        cron_schedule=meta.get("cron_schedule"),
        cron_enabled=meta.get("cron_enabled", False),
        undefined_queue_cap=meta.get("undefined_queue_cap", 100),
        max_run_logs=meta.get("max_run_logs", 50),
        node_count=meta.get("node_count", 0),
        edge_count=meta.get("edge_count", 0),
    )


def _skill_to_response(skill: Skill) -> SkillResponse:
    return SkillResponse(
        skill_id=skill.skill_id,
        name=skill.name,
        description=skill.description,
        version=skill.version,
        created_at=skill.created_at.isoformat() + "Z",
        updated_at=skill.updated_at.isoformat() + "Z",
        tags=skill.tags,
        required_capability=skill.required_capability.value,
    )


def _skill_to_detail_response(skill: Skill) -> SkillDetailResponse:
    base = _skill_to_response(skill)
    return SkillDetailResponse(
        **base.model_dump(),
        script=skill.script,
        input_schema=skill.input_schema,
        output_schema=skill.output_schema,
    )


def _skill_meta_to_response(meta: Dict[str, Any]) -> SkillResponse:
    return SkillResponse(
        skill_id=meta["skill_id"],
        name=meta["name"],
        description=meta.get("description", ""),
        version=meta.get("version", "1.0.0"),
        created_at=meta.get("created_at", "") or "",
        updated_at=meta.get("updated_at", "") or "",
        tags=meta.get("tags", []),
        required_capability=meta.get("required_capability", "generate"),
    )


# Import GraphEdge here for validation
from api.models.studio import GraphEdge