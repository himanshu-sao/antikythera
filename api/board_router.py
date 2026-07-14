import json
from fastapi import APIRouter, HTTPException, Response, Request, Body
from fastapi.responses import FileResponse
from typing import List, Dict, Any, Optional
import os
import re
from api.schemas import CreateItemRequest, MoveRequest, ReorderRequest, UpdateItemRequest, CommentRequest
from api.constants import VALID_ARTIFACTS
from api.utils import get_timeline_path
from api.workflow_state_manager import WorkflowStateManager

router = APIRouter(prefix="/api", tags=["Board Items"])

# Initialize manager
# State manager is obtained via the getter to allow test overrides
from api.main import get_state_manager

@router.get("/state", summary="Get full pipeline state")
async def get_state(request: Request):
    try:
        return get_state_manager().load_state()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load state: {str(e)}")

@router.post("/items", summary="Create new pipeline item")
async def create_item(request: Request, item_request: CreateItemRequest):
    success = get_state_manager().create_item(
        item_request.item_id,
        item_request.title,
        goal=item_request.goal,
        description=item_request.description,
        source_type=item_request.source_type,
        source_value=item_request.source_value,
        due_date=item_request.due_date,
        complexity=item_request.complexity
    )
    if not success:
        raise HTTPException(status_code=400, detail="Item already exists")
    return {"status": "success", "message": f"Item {item_request.item_id} created"}

@router.patch("/item/{item_id}", summary="Update item details")


async def update_item(request: Request, item_id: str, item_request: UpdateItemRequest):
    normalized_id = item_id.upper()
    updates = item_request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    success = get_state_manager().update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} updated"}

@router.patch("/item/{item_id}/name", summary="Update item name (title)")
async def update_item_name(request: Request, item_id: str, payload: dict = Body(...)):
    normalized_id = item_id.upper()
    name = payload.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing 'name' field")
    updates = {"title": name}
    success = get_state_manager().update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} name updated"}

@router.delete("/item/{item_id}", summary="Delete pipeline item")
async def delete_item(request: Request, item_id: str):
    normalized_id = item_id.upper()
    success = get_state_manager().delete_item(normalized_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} deleted"}

@router.post("/item/{item_id}/comment", summary="Add comment to item")
async def add_comment(request: Request, item_id: str, comment_request: CommentRequest):
    normalized_id = item_id.upper()
    comment = get_state_manager().add_comment(normalized_id, comment_request.author, comment_request.body)
    if not comment:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "comment": comment}

@router.delete("/item/{item_id}/comment/{comment_id}", summary="Delete comment")
async def delete_comment(request: Request, item_id: str, comment_id: str):
    normalized_id = item_id.upper()
    success = get_state_manager().delete_comment(normalized_id, comment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Item or comment not found")
    return {"status": "success", "message": f"Comment {comment_id} deleted"}

@router.post("/move", summary="Move item to stage")
async def move_item(request: Request, move_request: MoveRequest):
    normalized_id = move_request.item_id.upper()
    updates: dict = {"stage": move_request.new_stage}
    if move_request.order is not None:
        updates["order"] = move_request.order
    success = get_state_manager().update_item(normalized_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "success", "message": f"Item {normalized_id} moved to {move_request.new_stage}"}

@router.post("/items/reorder", summary="Bulk reorder items")
async def reorder_items(request: Request, reorder_request: ReorderRequest):
    get_state_manager().reorder_items(reorder_request.stage, reorder_request.ordered_ids)
    return {"status": "success", "message": f"Reordered {len(reorder_request.ordered_ids)} items in {reorder_request.stage}"}

@router.get("/item/{item_id}", summary="Get item details")
async def get_item(request: Request, item_id: str):
    normalized_id = item_id.upper()
    item = get_state_manager().get_item_details(normalized_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@router.get("/item/{item_id}/artifact/{artifact_name}", summary="Get item artifact")
async def get_artifact(item_id: str, artifact_name: str):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    if artifact_name not in VALID_ARTIFACTS:
        raise HTTPException(status_code=400, detail="Invalid artifact name")
    # Verify the item exists in the Kanban board; otherwise treat as missing
    from api.main import get_state_manager
    if not get_state_manager().get_item_details(item_id):
        return Response(status_code=204)
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    if not os.path.exists(artifact_path):
        return Response(status_code=204)
    return FileResponse(artifact_path)

@router.post("/item/{item_id}/artifact/{artifact_name}/content", summary="Update artifact content")
async def update_artifact_content(item_id: str, artifact_name: str, request: dict):
    item_id = item_id.upper()
    if not re.match(r'^[A-Z0-9-]+$', item_id):
        raise HTTPException(status_code=400, detail="Invalid item ID")
    if artifact_name != "review.md":
        raise HTTPException(status_code=400, detail="Only review.md can be edited")
    content = request.get("content")
    if content is None:
        raise HTTPException(status_code=400, detail="Missing content field")
    # Ensure the item exists in Kanban; otherwise it's an invalid operation
    from api.main import get_state_manager
    if not get_state_manager().get_item_details(item_id):
        raise HTTPException(status_code=500, detail="Item not found for update")
    artifact_path = os.path.join(os.path.dirname(__file__), "..", "automation-ideas", "requirements", item_id, artifact_name)
    temp_path = artifact_path + ".tmp"
    try:
        with open(temp_path, "w") as f:
            f.write(content)
        os.replace(temp_path, artifact_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    return {"status": "success", "message": f"Updated {artifact_name} for {item_id}"}

@router.post("/item/{item_id}/inline-output", summary="Update inline output")
async def update_inline_output(item_id: str, content: str):
    normalized_id = item_id.upper()
    from agents.state import load_state, save_state
    state = load_state()
    if normalized_id not in state["items"]:
        raise HTTPException(status_code=404, detail="Item not found")
    state["items"][normalized_id]["inline_output"] = content
    save_state(state)
    return {"message": "Inline output updated"}

@router.post("/item/{item_id}/promote-pattern", summary="Promote artifact to pattern")
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

@router.get("/item/{item_id}/timeline", summary="Get task timeline")
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
