from fastapi import APIRouter, HTTPException, Request
from api.main import get_state_manager
from typing import List, Dict, Any, Optional
import os

router = APIRouter(prefix="/api", tags=["Workflows"])

@router.get("/state", summary="Get the current Kanban state")
async def get_state(request: Request):
    try:
        state_manager = get_state_manager()
        return state_manager.load_state()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/workflows/templates/{template_id}", summary="Delete a workflow template")
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

@router.get("/workflows/templates", summary="List all workflow templates")
async def list_templates(request: Request):
    try:
        state_manager = get_state_manager()
        return state_manager.templates.list_templates()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/templates/{template_id}", summary="Get a specific template")
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

@router.post("/workflows/templates", summary="Create or update a template")
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

@router.get("/workflows/runs/{run_id}", summary="Get run details and summary")
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

@router.get("/workflows/runs/{run_id}/timeline", summary="Get only the run timeline")
async def get_run_timeline(request: Request, run_id: str):
    try:
        state_manager = get_state_manager()
        timeline = state_manager.runs.get_run_timeline(run_id)
        return timeline
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workflows/items/{item_id}/run", summary="Find the run associated with a Kanban item")
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
