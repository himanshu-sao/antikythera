from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from api.main import get_state_manager
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])


class TriggerWorkflowRequest(BaseModel):
    """UI-triggered run: execute a known template by id."""
    template_id: str
    inputs: Dict[str, Any] = {}


@router.post("/trigger", summary="Trigger a workflow run from a template")
async def trigger_workflow(req: TriggerWorkflowRequest):
    """UI calls this with {template_id, inputs}; returns {status, run_id, message}."""
    try:
        state_manager = get_state_manager()
        template = state_manager.templates.get_template(req.template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template '{req.template_id}' not found")
        run_id = f"run_{int.from_bytes(os.urandom(4), 'big')}"
        run_data = {
            "template_id": req.template_id,
            "status": "RUNNING",
            "current_step": 0,
            "trigger_payload": {"source": "ui", "inputs": req.inputs},
            "retry_count": 0,
        }
        state_manager.runs.create_run(run_id, run_data)
        # Optionally bind to a board item if the UI provided one in inputs.
        item_id = req.inputs.get("item_id")
        if item_id:
            state_manager.bindings.bind_run_to_item(run_id, str(item_id))
        return {"status": "success", "run_id": run_id, "message": f"Workflow '{req.template_id}' triggered"}
    except HTTPException:
        raise
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
