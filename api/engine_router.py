from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter(prefix="/api/engine", tags=["execution_engine"])

class StartRunRequest(BaseModel):
    template_id: str
    inputs: Dict[str, Any]

@router.post("/start")
async def start_workflow_run(request: StartRunRequest, req: Request):
    engine = req.app.state.engine
    try:
        run_id = engine.start_run(request.template_id, request.inputs)
        return {"status": "success", "run_id": run_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/run/{run_id}")
async def get_run_status(run_id: str, req: Request):
    run_manager = req.app.state.state_manager.runs
    run = run_manager.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
