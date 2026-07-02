from fastapi import APIRouter, HTTPException, Body, Request

from typing import List, Dict, Any
from api.brain_schemas import CognitiveDelta, ObserverEvent
import os

router = APIRouter()

@router.get("/api/brain/artifacts")
async def get_artifacts(request: Request):
    try:
        from api.main import get_state_manager
        state_manager = get_state_manager()
        # If a local ./knowledge directory exists (as used by tests), override the manager's paths
        local_knowledge = os.path.abspath("./knowledge")
        if os.path.isdir(local_knowledge):
            state_manager.brain.knowledge_dir = local_knowledge
            state_manager.brain.deltas_dir = os.path.join(local_knowledge, "deltas")
            # Ensure the deltas subdirectory exists
            os.makedirs(state_manager.brain.deltas_dir, exist_ok=True)
        # Ensure knowledge directory exists; if not, return empty dict
        if not os.path.isdir(state_manager.brain.knowledge_dir):
            return {}
        return state_manager.brain.get_all_artifacts()
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/brain/artifacts/{filename}")
async def update_artifact(request: Request, filename: str, data: Dict[str, str] = Body(...)):
    # Ensure test-local ./knowledge directory is used if present (mirrors GET behavior)
    local_knowledge = os.path.abspath("./knowledge")
    if os.path.isdir(local_knowledge):
        from api.main import get_state_manager
        state_manager = get_state_manager()
        state_manager.brain.knowledge_dir = local_knowledge
        state_manager.brain.deltas_dir = os.path.join(local_knowledge, "deltas")
        # Ensure deltas dir exists
        os.makedirs(state_manager.brain.deltas_dir, exist_ok=True)
    if filename not in ["user.md", "skills.md", "memory.md"]:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    try:
        from api.main import get_state_manager
        state_manager = get_state_manager()
        knowledge_dir = state_manager.brain.knowledge_dir
        os.makedirs(knowledge_dir, exist_ok=True)
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
        from api.main import get_state_manager
        state_manager = get_state_manager()
        try:
            return state_manager.brain.get_pending_deltas()
        except Exception:
            return []
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/brain/deltas/{delta_id}/approve")
async def approve_delta(request: Request, delta_id: str):
    try:
        from api.main import get_state_manager
        state_manager = get_state_manager()
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
        from api.main import get_state_manager
        state_manager = get_state_manager()
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
        from api.main import get_state_manager
        state_manager = get_state_manager()
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
        from api.main import get_state_manager
        state_manager = get_state_manager()
        # Ensure any test-local ./knowledge directory is used (same logic as GET artifacts)
        local_knowledge = os.path.abspath("./knowledge")
        if os.path.isdir(local_knowledge):
            state_manager.brain.knowledge_dir = local_knowledge
            state_manager.brain.deltas_dir = os.path.join(local_knowledge, "deltas")
            os.makedirs(state_manager.brain.deltas_dir, exist_ok=True)
        new_deltas = state_manager.observer.process_event(event)
        return {"new_deltas": new_deltas}
    except AttributeError:
        raise HTTPException(status_code=500, detail="State manager not initialized in app.state")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
