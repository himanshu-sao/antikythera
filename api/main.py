import re
import os
import json
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from api.state_manager import StateManager
from fastapi.responses import FileResponse

app = FastAPI(title="Hermes Kanban API")

# ENH-02: CORS middleware - allows the Vite dev server to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to pipeline-state.json from the api directory
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "pipeline-state.json")
state_manager = StateManager(STATE_PATH)

# Path for task logs
LOG_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "logs")

def get_timeline_path(item_id: str) -> str:
    return os.path.join(LOG_BASE_DIR, item_id.upper(), "timeline.jsonl")

# ENH-02: Valid pipeline stages for validation
VALID_STAGES = [
    "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
    "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
]

VALID_PRIORITIES = ["low", "medium", "high", "critical"]


class CreateItemRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(..., min_length=1, max_length=200)
    priority: Optional[str] = Field(default="medium")
    source_type: Optional[str] = Field(default=None)
    source_value: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('item_id')
    @classmethod
    def item_id_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["low", "medium", "high", "critical"]:
            raise ValueError('priority must be "low", "medium", "high", or "critical"')
        return v.lower() if v else "medium"

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory", "text"]:
            raise ValueError('source_type must be "url", "directory", or "text"')
        return v.lower() if v else None


class MoveRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50)
    new_stage: str = Field(...)
    order: Optional[int] = Field(default=None, ge=0)

    @field_validator('new_stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()


class ReorderRequest(BaseModel):
    stage: str = Field(...)
    ordered_ids: List[str] = Field(..., min_length=1)

    @field_validator('stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()


class UpdateItemRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default=None)
    confidence_score: Optional[int] = Field(default=None, ge=0, le=100)
    source_type: Optional[str] = Field(default=None)
    source_value: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None, pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.lower() not in VALID_PRIORITIES:
            raise ValueError(f'Invalid priority. Must be one of: {VALID_PRIORITIES}')
        return v
    
    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory", "text"]:
            raise ValueError('source_type must be "url", "directory", or "text"')
        return v.lower() if v else None


class CommentRequest(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=5000)


@app.get("/health")
async def health_check():
    try:
        _ = state_manager.load_state()
        return {"status": "healthy", "service": "hermes-kanban-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/api/state", summary="Get full pipeline state")
async def get_state():
    return state_manager.load_state()


@app.post("/api/items", summary="Create new pipeline item")
async def create_item(request: CreateItemRequest):
    success = state_manager.create_item(
        request.item_id,
        request.title,
        request.source_type,
        request.source_value,
        request.due_date
    )
    if not success:
        raise HTTPException(status_code=400, detail="Item already exists")
    return {"status": "success", "message": f"Item {request.item_id} created"}


@app.patch("/api/item/{item_id}", summary="Update item details")
async def update_item(item_id: str, request: UpdateItemRequest):
    normalized_id = item_id.upper()
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    success = state_manager.update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} updated"}


@app.delete("/api/item/{item_id}", summary="Delete pipeline item")
async def delete_item(item_id: str):
    normalized_id = item_id.upper()
    success = state_manager.delete_item(normalized_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} deleted"}


@app.post("/api/item/{item_id}/comment", summary="Add comment to item")
async def add_comment(item_id: str, request: CommentRequest):
    normalized_id = item_id.upper()
    comment = state_manager.add_comment(normalized_id, request.author, request.body)
    if not comment:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "comment": comment}


@app.delete("/api/item/{item_id}/comment/{comment_id}", summary="Delete comment")
async def delete_comment(item_id: str, comment_id: str):
    normalized_id = item_id.upper()
    success = state_manager.delete_comment(normalized_id, comment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item or comment not found")
    return {"status": "success", "message": f"Comment {comment_id} deleted"}


@app.post("/api/move", summary="Move item to stage")
async def move_item(request: MoveRequest):
    normalized_id = request.item_id.upper()
    updates: dict = {"stage": request.new_stage}
    if request.order is not None:
        updates["order"] = request.order
    success = state_manager.update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} moved to {request.new_stage}"}


@app.post("/api/items/reorder", summary="Bulk reorder items")
async def reorder_items(request: ReorderRequest):
    state_manager.reorder_items(request.stage, request.ordered_ids)
    return {"status": "success", "message": f"Reordered {len(request.ordered_ids)} items in {request.stage}"}


@app.get("/api/item/{item_id}", summary="Get item details")
async def get_item(item_id: str):
    normalized_id = item_id.upper()
    item = state_manager.get_item_details(normalized_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/api/item/{item_id}/artifact/{artifact_name}", summary="Get item artifact")
async def get_artifact(item_id: str, artifact_name: str):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    valid_artifacts = ["spec.md", "architecture.md", "tests.md", "review.md", "execution_report.md", "deliverables.md"]
    if artifact_name not in valid_artifacts:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    if not os.path.exists(artifact_path):
        from fastapi import Response
        return Response(status_code=204)
    return FileResponse(artifact_path)


@app.post("/api/item/{item_id}/artifact/{artifact_name}/content", summary="Update artifact content", description="Writes new content to a specific artifact. Only review.md is editable via this endpoint.")
async def update_artifact_content(item_id: str, artifact_name: str, request: dict):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    
    # Only review.md is allowed to be updated via this endpoint to prevent manual tampering with technical specs.
    if artifact_name != "review.md":
        raise HTTPException(status_code=400, detail="Only review.md can be edited")

    content = request.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Missing content field")
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    temp_path = artifact_path + ".tmp"
    try:
        with open(temp_path, "w") as f:
            f.write(content)
        os.replace(temp_path, artifact_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    return {"status": "success", "message": f"Updated {artifact_name} for {item_id}"}


@app.post("/api/item/{item_id}/inline-output", summary="Update inline output")
async def update_inline_output(item_id: str, content: str):
    normalized_id = item_id.upper()
    from agents.state import load_state, save_state
    state = load_state()
    if normalized_id not in state["items"]:
        raise HTTPException(status_code=404, detail="Item not found")
    
    state["items"][normalized_id]["inline_output"] = content
    save_state(state)
    return {"message": "Inline output updated"}


@app.post("/api/item/{item_id}/promote-pattern", summary="Promote artifact to pattern")
async def promote_pattern(item_id: str, artifact_name: str):
    from agents.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    
    valid_artifacts = ["spec.md", "architecture.md", "tests.md"]
    if artifact_name not in valid_artifacts:
         raise HTTPException(status_code=400, detail="Only spec, architecture, or tests can be promoted to patterns.")

    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    if not os.path.exists(artifact_path):
        raise HTTPException(status_code=404, detail="Artifact not found")

    try:
        with open(artifact_path, "r") as f:
            content = f.read()
        
        success = orchestrator.promote_artifact_to_pattern(item_id, artifact_name, content)
        
        if not success:
            raise HTTPException(status_code=500, detail="Pattern promotion failed")
            
        return {"status": "success", "message": f"Successfully promoted {artifact_name} to patterns."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/item/{item_id}/timeline", summary="Get task timeline", description="Retrieves the structured execution log (JSONL) for a specific task.")
async def get_item_timeline(item_id: str):
    normalized_id = item_id.upper()
    timeline_path = get_timeline_path(normalized_id)
    
    if not os.path.exists(timeline_path):
        return []
    
    try:
        timeline = []
        with open(timeline_path, "r") as f:
            for line in f:
                if line.strip():
                    timeline.append(json.loads(line))
        return timeline
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read timeline: {str(e)}")
