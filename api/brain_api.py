from fastapi import APIRouter, HTTPException, Body, Request
from typing import List, Dict, Any
from api.brain_schemas import CognitiveDelta, ObserverEvent
import os

router = APIRouter()

@router.get("/api/brain/artifacts")
async def get_artifacts(request: Request):
    try:
        state_manager = request.app.state.state_manager
        return state_manager.brain.get_all_artifacts()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/brain/artifacts/{filename}")
async def update_artifact(request: Request, filename: str, data: Dict[str, str] = Body(...)):
    if filename not in ["user.md", "skills.md", "memory.md"]:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    try:
        state_manager = request.app.state.state_manager
        knowledge_dir = state_manager.brain.knowledge_dir
        # For inline edits, we just write directly
        content = data.get("content", "")
        path = os.path.join(knowledge_dir, filename)
        with open(path, 'w') as f:
            f.write(content)
        return {"success": True}
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/brain/deltas/pending")
async def get_pending_deltas(request: Request):
    try:
        state_manager = request.app.state.state_manager
        return state_manager.brain.get_pending_deltas()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/approve")
async def approve_delta(request: Request, delta_id: str):
    try:
        state_manager = request.app.state.state_manager
        if state_manager.brain.commit_delta(delta_id):
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Delta not found")
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/reject")
async def reject_delta(request: Request, delta_id: str):
    try:
        state_manager = request.app.state.state_manager
        if state_manager.brain.reject_delta(delta_id):
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Delta not found")
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/refine")
async def refine_delta(request: Request, delta_id: str, data: Dict[str, str] = Body(...)):
    comment = data.get("comment", "")
    if not comment:
        raise HTTPException(status_code=400, detail="comment is required")
    try:
        state_manager = request.app.state.state_manager
        updated_delta = state_manager.brain.refine_delta(delta_id, comment)
        return updated_delta
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# In a real system, the observer would have an endpoint to ingest events
@router.post("/api/observer/event")
async def ingest_event(request: Request, event: ObserverEvent = Body(...)):
    try:
        state_manager = request.app.state.state_manager
        new_deltas = state_manager.observer.process_event(event)
        return {"new_deltas": new_deltas}
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
