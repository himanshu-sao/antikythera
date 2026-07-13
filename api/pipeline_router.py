from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from .models.automation import Pipeline, Path, PathStep, PipelineRun
import uuid
from datetime import datetime
import os

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
os.makedirs(BASE_DIR, exist_ok=True)
# P3.4: removed dead `from .secret_vault import SecretVault` + `vault = SecretVault(BASE_DIR)`
# instantiation here — unused, and they created `.vault.key`/`secrets.vault` on disk at import.

router = APIRouter()

# In-memory stores for demonstration
pipelines_db: Dict[str, Pipeline] = {}
paths_db: Dict[str, Path] = {}
runs_db: Dict[str, PipelineRun] = {}  # NEW: Store pipeline runs

class PromotePathRequest(BaseModel):
    """Path data for promotion (without pipeline_id which is assigned on promotion)"""
    path_id: str
    name: str
    steps: List[PathStep] = []
    is_active: bool = True

class PromotePipelineRequest(BaseModel):
    name: str
    description: Optional[str] = None
    paths: List[PromotePathRequest]  # Changed from List[Path]
    trigger: Dict[str, Any]  # { "type": "CRON", "config": { "cron": "0 9 * * *" } }
    global_context: Dict[str, str] = {}

class PipelineUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger: Optional[Dict[str, Any]] = None
    global_context: Optional[Dict[str, str]] = None

@router.post("/promote")
async def promote_to_pipeline(request: PromotePipelineRequest):
    """
    Promotes a set of recorded paths into a production Pipeline.
    """
    pipeline_id = f"pipe_{uuid.uuid4().hex[:8]}"
    
    # 1. Save Paths first (convert PromotePathRequest to Path)
    path_ids = []
    for p_req in request.paths:
        p_id = f"path_{uuid.uuid4().hex[:8]}"
        # Convert to Path model with pipeline_id assigned
        path = Path(
            path_id=p_id,
            pipeline_id=pipeline_id,  # Assign the new pipeline_id
            name=p_req.name,
            steps=p_req.steps,
            is_active=p_req.is_active
        )
        paths_db[p_id] = path
        path_ids.append(p_id)
    
    # 2. Create Pipeline
    pipeline = Pipeline(
        pipeline_id=pipeline_id,
        name=request.name,
        description=request.description,
        paths=path_ids,
        trigger=request.trigger,
        global_context=request.global_context,
        status="ACTIVE"
    )
    
    pipelines_db[pipeline_id] = pipeline
    
    return {
        "status": "promoted",
        "pipeline_id": pipeline_id,
        "path_ids": path_ids
    }

@router.get("/")
async def list_pipelines():
    return list(pipelines_db.values())

@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_db[pipeline_id]
    # Enrich with actual path data
    return {
        "pipeline": pipeline,
        "paths": [paths_db[pid] for pid in pipeline.paths if pid in paths_db]
    }

@router.patch("/{pipeline_id}")
async def update_pipeline(pipeline_id: str, request: PipelineUpdateRequest):
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_db[pipeline_id]
    if request.name: pipeline.name = request.name
    if request.description: pipeline.description = request.description
    if request.trigger: pipeline.trigger = request.trigger
    if request.global_context: pipeline.global_context = request.global_context
    
    pipelines_db[pipeline_id] = pipeline
    return {"status": "updated", "pipeline": pipeline}

@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    if pipeline_id in pipelines_db:
        del pipelines_db[pipeline_id]
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Pipeline not found")

# === Execution Monitoring Endpoints (Task 4.3) ===

@router.post("/{pipeline_id}/run")
async def trigger_pipeline_run(pipeline_id: str):
    """
    Manually trigger a pipeline execution.
    In production, this would be called by the scheduler via trigger_manager.
    """
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_db[pipeline_id]
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    
    # Create initial run record
    run = PipelineRun(
        run_id=run_id,
        pipeline_id=pipeline_id,
        started_at=datetime.utcnow(),
        status="RUNNING",
        logs=[{"timestamp": datetime.utcnow().isoformat(), "level": "INFO", "message": f"Pipeline execution started: {pipeline.name}"}]
    )
    runs_db[run_id] = run
    
    # TODO: In production, this would trigger the actual execution_engine
    # For now, we just return the run_id
    
    return {
        "status": "running",
        "run_id": run_id,
        "pipeline_id": pipeline_id
    }

@router.get("/{pipeline_id}/runs")
async def list_pipeline_runs(pipeline_id: str, limit: int = 10):
    """
    Get the last N runs for a pipeline.
    """
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # Filter runs for this pipeline and sort by started_at descending
    pipeline_runs = [
        run for run in runs_db.values() 
        if run.pipeline_id == pipeline_id
    ]
    pipeline_runs.sort(key=lambda r: r.started_at, reverse=True)
    
    return pipeline_runs[:limit]

@router.get("/{pipeline_id}/runs/{run_id}")
async def get_pipeline_run(pipeline_id: str, run_id: str):
    """
    Get details of a specific pipeline run.
    """
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if run_id not in runs_db:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = runs_db[run_id]
    if run.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Run not found for this pipeline")
    
    return run

@router.post("/{pipeline_id}/runs/{run_id}/complete")
async def complete_pipeline_run(pipeline_id: str, run_id: str, status: str, error: Optional[str] = None):
    """
    Mark a pipeline run as complete (called by execution engine).
    """
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if run_id not in runs_db:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = runs_db[run_id]
    if run.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Run not found for this pipeline")
    
    if status not in ["SUCCESS", "FAILED"]:
        raise HTTPException(status_code=400, detail="Status must be SUCCESS or FAILED")
    
    # Update run
    run.status = status
    run.ended_at = datetime.utcnow()
    run.error = error
    run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
    
    # Add completion log
    run.logs.append({
        "timestamp": run.ended_at.isoformat(),
        "level": "INFO" if status == "SUCCESS" else "ERROR",
        "message": f"Pipeline execution {status.lower()}" + (f": {error}" if error else "")
    })
    
    runs_db[run_id] = run
    
    return {"status": "completed", "run_id": run_id, "final_status": status}

@router.post("/{pipeline_id}/runs/{run_id}/log")
async def add_run_log(pipeline_id: str, run_id: str, level: str, message: str):
    """
    Add a log entry during pipeline execution.
    """
    if pipeline_id not in pipelines_db:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if run_id not in runs_db:
        raise HTTPException(status_code=404, detail="Run not found")
    
    run = runs_db[run_id]
    if run.pipeline_id != pipeline_id:
        raise HTTPException(status_code=404, detail="Run not found for this pipeline")
    
    if level not in ["INFO", "WARNING", "ERROR", "DEBUG"]:
        raise HTTPException(status_code=400, detail="Invalid log level")
    
    run.logs.append({
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message
    })
    
    runs_db[run_id] = run
    
    return {"status": "logged"}
