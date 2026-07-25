from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.main import get_state_manager
from typing import Dict, Any, List, Optional
import jsonschema
from jsonschema import validate, ValidationError

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# Server-side adapter allowlist for template saving (B1 hardening)
# Excludes execution-capable adapters: 'shell' (not in registry, errors at runtime)
# and 'bob_shell' (executes commands via BOB CLI).
# The builder router generates lowercase adapter tokens; workflow_engine uses uppercase keys.
ALLOWED_TEMPLATE_ADAPTERS = frozenset({"internal", "github", "jira", "ai"})

# B2: Per-adapter JSON schemas for step.config validation
# These schemas define the allowed config fields for each adapter.
# They are used to validate templates at save time (POST /api/workflows/templates).
ADAPTER_CONFIG_SCHEMAS = {
    "internal": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["move_item", "add_comment", "list_items"]},
            "item_id": {"type": "string"},
            "new_stage": {"type": "string", "enum": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]},
            "author": {"type": "string"},
            "body": {"type": "string"},
            "stage": {"type": "string", "enum": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]},
        },
        "required": ["action"],
        "additionalProperties": False,
    },
    "github": {
        "type": "object",
        "properties": {
            # list_repos
            "org": {"type": "string"},
            "type": {"type": "string", "enum": ["all", "public", "private", "forks", "sources", "member"]},
            "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
            # list_pull_requests
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "state": {"type": "string", "enum": ["open", "closed", "all"]},
            # create (create repo)
            "name": {"type": "string"},
            "description": {"type": "string"},
            "private": {"type": "boolean"},
            # update/delete (resource_id)
            "resource_id": {"type": "string"},
        },
        "required": [],  # action-dependent, validated at runtime
        "additionalProperties": False,
    },
    "jira": {
        "type": "object",
        "properties": {
            # list_tickets
            "jql": {"type": "string"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
            # list_projects (no additional config)
            # fetch (single issue)
            "resource_id": {"type": "string"},
            # update (transition, assign, comment)
            "transition": {"type": "string"},
            "assignee": {"type": "string"},
            "comment": {"type": "string"},
            # create
            "project_key": {"type": "string"},
            "issue_type": {"type": "string"},
            "summary": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": [],
        "additionalProperties": False,
    },
    "ai": {
        "type": "object",
        "properties": {
            # analyze action (the only action for ai adapter currently)
            "prompt": {"type": "string"},
            "context": {"type": "object"},
            "patterns": {"type": "array", "items": {"type": "object"}},
        },
        "required": [],
        "additionalProperties": False,
    },
}


def _validate_template_adapters(template: Dict[str, Any]) -> list[str]:
    """Validate all step adapters against the allowlist. Returns list of violations."""
    violations = []
    for step in template.get("steps", []):
        adapter = step.get("adapter", "").lower().strip()
        if adapter and adapter not in ALLOWED_TEMPLATE_ADAPTERS:
            violations.append(f"step {step.get('id', '?')}: adapter '{adapter}' not in allowlist {sorted(ALLOWED_TEMPLATE_ADAPTERS)}")
    return violations


def _validate_step_configs(template: Dict[str, Any]) -> list[str]:
    """
    B2: Validate step.config against per-adapter JSON schemas.
    Returns list of violations (empty if all valid).
    """
    violations = []
    for step in template.get("steps", []):
        adapter = step.get("adapter", "").lower().strip()
        if not adapter:
            continue  # Empty adapter is allowed (B1 validation handles it separately)

        schema = ADAPTER_CONFIG_SCHEMAS.get(adapter)
        if not schema:
            # No schema defined for this adapter - skip config validation
            continue

        config = step.get("config", {})
        if not isinstance(config, dict):
            violations.append(f"step {step.get('id', '?')}: config must be an object")
            continue

        # Check for duplicate fields in config (JSON objects can't have duplicates in Python dict,
        # but we check for the edge case where the template might have been constructed with duplicates)
        # This is mainly a defensive check since Python dicts don't preserve duplicates.

        # Validate against JSON schema
        try:
            validate(instance=config, schema=schema)
        except ValidationError as e:
            # Provide a clear error message with the field path
            field_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            violations.append(f"step {step.get('id', '?')}: config validation failed at '{field_path}': {e.message}")

    return violations



# NOTE: GET /api/state is served by board_router.py — do not duplicate here.


class TriggerRequest(BaseModel):
    template_id: str
    inputs: Dict[str, Any] = {}

@router.delete("/templates/{template_id}", summary="Delete a workflow template")
async def delete_template(request: Request, template_id: str):
    try:
        state_manager = get_state_manager()
        if state_manager.templates.delete_template(template_id):
            return {"status": "success", "message": f"Template {template_id} deleted"}
        raise HTTPException(status_code=404, detail="Template not found")
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates", summary="List all workflow templates")
async def list_templates(request: Request):
    try:
        state_manager = get_state_manager()
        return state_manager.templates.list_templates()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/templates/{template_id}", summary="Get a specific template")
async def get_template(request: Request, template_id: str):
    try:
        state_manager = get_state_manager()
        template = state_manager.templates.get_template(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        return template
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/templates", summary="Create or update a template")
async def save_template(request: Request, template: Dict[str, Any]):
    template_id = template.get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")

    # B1: server-side adapter allowlist validation
    violations = _validate_template_adapters(template)
    if violations:
        raise HTTPException(
            status_code=422,
            detail={"message": "Template contains disallowed adapters", "violations": violations}
        )

    # B2: per-adapter step.config schema validation
    config_violations = _validate_step_configs(template)
    if config_violations:
        raise HTTPException(
            status_code=422,
            detail={"message": "Template step config validation failed", "violations": config_violations}
        )

    try:
        state_manager = get_state_manager()
        if state_manager.templates.save_template(template_id, template):
            return {"status": "success", "message": f"Template {template_id} saved"}
        raise HTTPException(status_code=500, detail="Failed to save template")
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}", summary="Get run details and summary")
async def get_run_details(request: Request, run_id: str):
    try:
        state_manager = get_state_manager()
        run = state_manager.runs.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        template = state_manager.templates.get_template(run.get("template_id", ""))
        timeline = state_manager.runs.get_run_timeline(run_id)
        bindings = state_manager.bindings.get_bindings_for_run(run_id)

        return {
            "run": run,
            "template": template,
            "timeline": timeline,
            "bindings": bindings
        }
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/runs/{run_id}/timeline", summary="Get only the run timeline")
async def get_run_timeline(request: Request, run_id: str):
    try:
        state_manager = get_state_manager()
        timeline = state_manager.runs.get_run_timeline(run_id)
        return timeline
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items/{item_id}/run", summary="Find the run associated with a Kanban item")
async def get_item_run(request: Request, item_id: str):
    try:
        state_manager = get_state_manager()
        run_id = state_manager.bindings.get_run_id_for_item(item_id)
        if not run_id:
            return {"run_id": None}
        return {"run_id": run_id}
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger", summary="Manually start a workflow run for a template")
async def trigger_workflow(request: Request, body: TriggerRequest):
    """
    Starts a real workflow run via the shared ``ExecutionEngine.start_run``
    (same path as ``/api/engine/start``). Unlike the ``/api/triggers/webhook``
    route — which synthesizes a template from an inbound provider payload —
    this endpoint requires an existing template_id and advances the run
    through ``process_next_step`` so it is not left as an idle RUNNING row.
    """
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise HTTPException(status_code=500, detail="Execution engine not initialized in app.state")
    try:
        run_id = engine.start_run(body.template_id, body.inputs)
        return {"status": "success", "run_id": run_id}
    except ValueError as e:
        # start_run raises ValueError when the template_id is unknown.
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
