from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from api.brain_managers import BrainManager, ObserverManager
from api.brain_schemas import CognitiveDelta, ObserverEvent
import os

router = APIRouter()

# Configuration - in real life these would be in a config file
KNOWLEDGE_DIR = os.path.abspath("./knowledge")
DELTAS_DIR = os.path.abspath("./knowledge/deltas")

brain_manager = BrainManager(KNOWLEDGE_DIR, DELTAS_DIR)
observer_manager = ObserverManager(brain_manager)

@router.get("/api/brain/artifacts")
async def get_artifacts():
    try:
        return brain_manager.get_all_artifacts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/brain/artifacts/{filename}")
async def update_artifact(filename: str, data: Dict[str, str] = Body(...)):
    if filename not in ["user.md", "skills.md", "memory.md"]:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    try:
        # For inline edits, we just write directly
        content = data.get("content", "")
        path = os.path.join(KNOWLEDGE_DIR, filename)
        with open(path, 'w') as f:
            f.write(content)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/brain/deltas/pending")
async def get_pending_deltas():
    try:
        return brain_manager.get_pending_deltas()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/approve")
async def approve_delta(delta_id: str):
    try:
        if brain_manager.commit_delta(delta_id):
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Delta not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/reject")
async def reject_delta(delta_id: str):
    try:
        if brain_manager.reject_delta(delta_id):
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Delta not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/refine")
async def refine_delta(delta_id: str, data: Dict[str, str] = Body(...)):
    comment = data.get("comment", "")
    if not comment:
        raise HTTPException(status_code=400, detail="comment is required")
    try:
        updated_delta = brain_manager.refine_delta(delta_id, comment)
        return updated_delta
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# In a real system, the observer would have an endpoint to ingest events
@router.post("/api/observer/event")
async def ingest_event(event: ObserverEvent = Body(...)):
    try:
        new_deltas = observer_manager.process_event(event)
        return {"new_deltas": new_deltas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
