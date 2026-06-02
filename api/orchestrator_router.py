from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, Optional
from pydantic import BaseModel
from api.workflow_state_manager import WorkflowStateManager
import os

router = APIRouter(prefix="/api/orchestrator", tags=["orchestrator"])

class TransitionRequest(BaseModel):
    item_id: str
    target_phase: str

class ProposalRequest(BaseModel):
    item_id: str
    proposal: Dict[str, Any]

@router.get("/{item_id}")
async def get_orchestrator_state(item_id: str, request: Request):
    state_manager: WorkflowStateManager = request.app.state.state_manager
    state = state_manager.load_state()
    item = state.items.get(item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {
        "item_id": item_id,
        "current_phase": item.get("current_phase", "DISCOVERY"),
        "proposal": item.get("current_proposal"),
        "item_data": item
    }

@router.post("/transition")
async def transition_phase(request: TransitionRequest, req: Request):
    state_manager: WorkflowStateManager = req.app.state.state_manager
    item = state_manager.get_item_details(request.item_id)
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    # Update phase and clear current proposal
    updates = {
        "current_phase": request.target_phase,
        "current_proposal": None 
    }
    
    success = state_manager.update_item(request.item_id, updates)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update item phase")
    
    # --- RESUME MECHANISM ---
    # If a recovery task (REC-*) reaches HANDOVER, signal the engine to resume the original run
    if request.target_phase == "HANDOVER" and request.item_id.startswith("REC-"):
        try:
            engine = req.app.state.engine
            resumed_run_id = engine.resume_run_by_item_id(request.item_id)
            print(f"🚨 RESUME SIGNAL: Recovery task {request.item_id} completed. Resuming WorkflowRun {resumed_run_id}...")
        except Exception as e:
            print(f"Warning: Failed to resume run for {request.item_id}: {e}")
    
    # Update the SSOT (TODO.md)
    try:
        update_todo_file(request.item_id, request.target_phase)
    except Exception as e:
        print(f"Warning: Failed to update TODO.md: {e}")
        
    return {"status": "success", "new_phase": request.target_phase}

@router.post("/propose")
async def propose_transaction(request: ProposalRequest, req: Request):
    state_manager: WorkflowStateManager = req.app.state.state_manager
    
    # Save the proposal into the item's state
    success = state_manager.update_item(
        request.item_id, 
        {"current_proposal": request.proposal}
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save proposal")
        
    return {"status": "success", "message": "Proposal pushed to UI"}

def update_todo_file(item_id: str, phase: str):
    todo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "TODO.md"))
    if not os.path.exists(todo_path):
        return
        
    with open(todo_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    updated = False
    for i, line in enumerate(lines):
        if item_id in line:
            lines[i] = line.replace("[ ]", "[x]") if "TODO" in line else line
            updated = True
            
    if updated:
        with open(todo_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
