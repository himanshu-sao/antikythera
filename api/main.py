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
    success = state_manager.update_item_stage(request.item_id, request.new_stage)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {request.item_id} moved to {request.new_stage}"}

@app.get("/api/item/{item_id}")
async def get_item(item_id: str):
    item = state_manager.get_item_details(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
