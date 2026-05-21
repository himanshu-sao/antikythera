import re
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from api.state_manager import StateManager
import os

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

# ENH-02: Valid pipeline stages for validation
VALID_STAGES = [
    "INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE",
    "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"
]

VALID_PRIORITIES = ["low", "medium", "high", "critical"]


class CreateItemRequest(BaseModel):
    # ENH-02: Add field length constraints and pattern validation
    item_id: str = Field(..., min_length=1, max_length=50, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(..., min_length=1, max_length=200)

    @field_validator('item_id')
    @classmethod
    def item_id_uppercase(cls, v: str) -> str:
        return v.upper()


class MoveRequest(BaseModel):
    item_id: str = Field(..., min_length=1, max_length=50)
    new_stage: str = Field(...)
    order: Optional[int] = Field(default=None, ge=0)  # ENH-05: carry target index for reordering

    @field_validator('new_stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()



# ENH-14: Health check endpoint for Docker
@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    try:
        # Verify state manager can load state
        _ = state_manager.load_state()
        return {"status": "healthy", "service": "hermes-kanban-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/api/state")
async def get_state():
    return state_manager.load_state()


class UpdateItemRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    priority: Optional[str] = Field(default=None)
    confidence_score: Optional[int] = Field(default=None, ge=0, le=100)
    source_type: Optional[str] = Field(default=None)
    source_value: Optional[str] = Field(default=None)

    @field_validator('priority')
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.lower() not in VALID_PRIORITIES:
            raise ValueError(f'Invalid priority. Must be one of: {VALID_PRIORITIES}')
        return v

    @field_validator('source_type')
    @classmethod
    def validate_source_type(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ["url", "directory"]:
            raise ValueError('source_type must be "url" or "directory"')
        return v.lower() if v else None


@app.post("/api/items")
async def create_item(request: CreateItemRequest):
    success = state_manager.create_item(
        request.item_id,
        request.title,
        request.source_type,
        request.source_value
    )
    if not success:
        raise HTTPException(status_code=400, detail="Item already exists")
    return {"status": "success", "message": f"Item {request.item_id} created"}


@app.patch("/api/item/{item_id}")
async def update_item(item_id: str, request: UpdateItemRequest):
    normalized_id = item_id.upper()
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    success = state_manager.update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} updated"}


# ENH-01: Delete item endpoint
@app.delete("/api/item/{item_id}")
async def delete_item(item_id: str):
    normalized_id = item_id.upper()
    success = state_manager.delete_item(normalized_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} deleted"}


class CommentRequest(BaseModel):
    author: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=5000)


@app.post("/api/item/{item_id}/comment")
async def add_comment(item_id: str, request: CommentRequest):
    normalized_id = item_id.upper()
    comment = state_manager.add_comment(normalized_id, request.author, request.body)
    if not comment:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "comment": comment}


# ENH-04: Delete comment endpoint
@app.delete("/api/item/{item_id}/comment/{comment_id}")
async def delete_comment(item_id: str, comment_id: str):
    normalized_id = item_id.upper()
    success = state_manager.delete_comment(normalized_id, comment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item or comment not found")
    return {"status": "success", "message": f"Comment {comment_id} deleted"}


@app.post("/api/move")
async def move_item(request: MoveRequest):
    normalized_id = request.item_id.upper()
    updates: dict = {"stage": request.new_stage}
    if request.order is not None:
        updates["order"] = request.order
    success = state_manager.update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} moved to {request.new_stage}"}


# ENH-05: Bulk reorder endpoint
class ReorderRequest(BaseModel):
    stage: str = Field(...)
    ordered_ids: List[str] = Field(..., min_length=1)

    @field_validator('stage')
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v.upper() not in VALID_STAGES:
            raise ValueError(f'Invalid stage. Must be one of: {VALID_STAGES}')
        return v.upper()


@app.post("/api/items/reorder")
async def reorder_items(request: ReorderRequest):
    state_manager.reorder_items(request.stage, request.ordered_ids)
    return {"status": "success", "message": f"Reordered {len(request.ordered_ids)} items in {request.stage}"}


@app.get("/api/item/{item_id}")
async def get_item(item_id: str):
    item_id = item_id.upper()
    item = state_manager.get_item_details(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/api/item/{item_id}/artifact/{artifact_name}")
async def get_artifact(item_id: str, artifact_name: str):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    valid_artifacts = ["spec.md", "architecture.md", "tests.md", "review.md"]
    if artifact_name not in valid_artifacts:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    if not os.path.exists(artifact_path):
        raise HTTPException(status_code=404, detail="Artifact not found")
    from fastapi.responses import FileResponse
    return FileResponse(artifact_path)


@app.post("/api/item/{item_id}/artifact/{artifact_name}/content")
async def update_artifact_content(item_id: str, artifact_name: str, request: dict):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
