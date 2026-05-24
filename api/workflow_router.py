from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from api.workflow_state_manager import WorkflowStateManager
import os

router = APIRouter(prefix="/api/workflows", tags=["Workflows"])

# Initialize manager using the project's state directory
STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
workflow_mgr = WorkflowStateManager(STATE_DIR)

@router.get("/templates", summary="List all workflow templates")
async def list_templates():
    return workflow_mgr.list_templates()

@router.get("/templates/{template_id}", summary="Get a specific template")
async def get_template(template_id: str):
    template = workflow_mgr.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.post("/templates", summary="Create or update a template")
async def save_template(template: Dict[str, Any]):
    template_id = template.get("template_id")
    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")
    if workflow_mgr.save_template(template_id, template):
        return {"status": "success", "message": f"Template {template_id} saved"}
    raise HTTPException(status_code=500, detail="Failed to save template")

@router.get("/runs/{run_id}", summary="Get run details and summary")
async def get_run_details(run_id: str):
    run = workflow_mgr.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    template = workflow_mgr.get_template(run.get("template_id", ""))
    timeline = workflow_mgr.get_run_timeline(run_id)
    bindings = workflow_mgr.get_bindings_for_run(run_id)
    
    return {
        "run": run,
        "template": template,
        "timeline": timeline,
        "bindings": bindings
    }

@router.get("/runs/{run_id}/timeline", summary="Get only the run timeline")
async def get_run_timeline(run_id: str):
    timeline = workflow_mgr.get_run_timeline(run_id)
    return timeline

@router.get("/items/{item_id}/run", summary="Find the run associated with a Kanban item")
async def get_item_run(item_id: str):
    run_id = workflow_mgr.get_run_id_for_item(item_id)
    if not run_id:
        return {"run_id": None}
    return {"run_id": run_id}
