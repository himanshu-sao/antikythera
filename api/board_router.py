import os
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException
from api.workflow_state_manager import WorkflowStateManager

router = APIRouter(prefix="/api/boards", tags=["Virtual Boards"])

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
workflow_mgr = WorkflowStateManager(BASE_DIR)

@router.get("/virtual/{template_id}", summary="Get a virtual board view for a specific template")
async def get_virtual_board(template_id: str):
    """
    Returns a filtered view of the pipeline board based on the template.
    Only items bound to runs of this template are returned.
    """
    # 1. Get all runs for this template
    # In a production system, we'd index this. For now, we scan.
    all_runs = workflow_mgr._load_json(workflow_mgr.runs_path, workflow_mgr._runs_lock)
    template_runs = [rid for rid, run in all_runs.items() if run.get("template_id") == template_id]
    
    # 2. Find all items bound to these runs
    all_bindings = workflow_mgr._load_json(workflow_mgr.bindings_path, workflow_mgr._bindings_lock)
    item_ids = set()
    for binding in all_bindings.values():
        if binding["run_id"] in template_runs:
            item_ids.add(binding["item_id"])
            
    # 3. Get the actual items from the state manager
    # This is a simulation of the 'Virtual Board' filter.
    state = workflow_mgr._load_json(workflow_mgr.state_path if hasattr(workflow_mgr, 'state_path') else os.path.join(BASE_DIR, "pipeline-state.json"), workflow_mgr._templates_lock)
    
    # We need to access the main pipeline state. Since StateManager uses internal paths, 
    # we'll assume the state is in the standard pipeline-state.json.
    state_path = os.path.join(BASE_DIR, "pipeline-state.json")
    if not os.path.exists(state_path):
        return {"items": [], "template_id": template_id}
        
    with open(state_path, "r") as f:
        full_state = json.load(f)
    
    filtered_items = [
        {"id": tid, **item} 
        for tid, item in full_state.get("items", {}).items() 
        if tid in item_ids
    ]
    
    return {
        "items": filtered_items,
        "template_id": template_id,
        "count": len(filtered_items)
    }
