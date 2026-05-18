import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from .state_manager import StateManager
import os

app = FastAPI(title="Hermes Kanban API")

# Path to pipeline-state.json from the api directory
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "pipeline-state.json")
state_manager = StateManager(STATE_PATH)

class MoveRequest(BaseModel):
    item_id: str
    new_stage: str

@app.get("/api/state")
async def get_state():
    return state_manager.load_state()

@app.post("/api/move")
async def move_item(request: MoveRequest):
    normalized_id = request.item_id.upper()
    success = state_manager.update_item_stage(normalized_id, request.new_stage)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} moved to {request.new_stage}"}

@app.get("/api/item/{item_id}")
async def get_item(item_id: str):
    item_id = item_id.upper()
    item = state_manager.get_item_details(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/item/{item_id}/artifact/{artifact_name}")
async def get_artifact(item_id: str, artifact_name: str):
    # Strict whitelist validation: only allow ID-XXX pattern (alphanumeric + hyphens)
    item_id = item_id.upper()
    if not re.match(r"^[A-Z0-9-]+$", item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")

    # Valid artifacts: spec.md, architecture.md, tests.md, review.md
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
    if not re.match(r"^[A-Z0-9-]+$", item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")

    if artifact_name != "review.md":
        raise HTTPException(status_code=400, detail="Only review.md can be edited")

    content = request.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Missing content field")

    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)

    # Atomic write using temp file
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
