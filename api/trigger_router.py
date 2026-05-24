import os
import json
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Request
from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub

router = APIRouter(prefix="/api/triggers", tags=["Triggers"])

# These will be initialized in main.py
state_manager: Optional[WorkflowStateManager] = None
hub: Optional[IntegrationHub] = None

def set_trigger_deps(sm: WorkflowStateManager, h: IntegrationHub):
    global state_manager, hub
    state_manager = sm
    hub = h

@router.post("/webhook/{provider}")
async def handle_webhook(provider: str, request: Request):
    """
    Public endpoint to receive webhooks from GitHub, Jira, etc.
    Maps the event to a workflow run.
    """
    if state_manager is None or hub is None:
        raise HTTPException(status_code=500, detail="Trigger system not initialized")
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # 1. Identify the template associated with this webhook
    # In a real system, we'd check a mapping table. For now, we simulate:
    template_id = "default_webhook_template"
    if "github" in provider.lower():
        template_id = "github_pr_release"
    elif "jira" in provider.lower():
        template_id = "jira_triage"
    
    # Create a dummy template if it doesn't exist to avoid 404 in audit
    template = state_manager.get_template(template_id)
    if not template:
        state_manager.save_template(template_id, {
            "name": f"Auto-generated {provider} Template",
            "trigger": {"type": "webhook", "provider": provider},
            "steps": []
        })
        template = state_manager.get_template(template_id)

    # 2. Create a new workflow run
    run_id = f"run_{int(os.urandom(4).hex(), 16)}"
    run_data = {
        "template_id": template_id,
        "status": "RUNNING",
        "current_step": 0,
        "trigger_payload": payload,
        "retry_count": 0
    }
    state_manager.create_run(run_id, run_data)
    
    # 3. Bind it to a board item
    item_id = payload.get("issue", {}).get("key") or payload.get("number") or "GENERIC_ITEM"
    state_manager.bind_run_to_item(run_id, str(item_id))
    
    return {"status": "success", "run_id": run_id, "message": "Workflow triggered via webhook"}
