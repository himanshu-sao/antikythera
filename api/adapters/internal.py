from typing import Dict, Any, Optional
from api.adapters.base import BaseAdapter

class InternalKanbanAdapter(BaseAdapter):
    """Concrete adapter for internal Kanban actions.

    Implements the abstract methods required by ``BaseAdapter`` so the
    class can be instantiated without errors. The async methods simply
    raise ``NotImplementedError`` because they are not used by the current
    workflow; the synchronous ``execute`` method provides the needed logic.
    """
    def __init__(self, vault=None):
        # ``BaseAdapter`` expects a ``vault`` argument but many internal uses
        # do not need it. Provide a default ``None`` to keep compatibility.
        super().__init__(vault)

    """Adapter for interacting with the Antikythera Kanban API itself."""
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Required: 'action' (e.g., 'move_item', 'add_comment')
        if "action" not in config:
            return False
        return True

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # This adapter interacts with the internal state manager directly for efficiency
        # rather than making HTTP calls to its own API.
        from api.state_manager import StateManager
        from api.workflow_state_manager import WorkflowStateManager
        
        action = config.get("action")
        item_id = config.get("item_id")
        
        # We need to find the item bound to this run
        # If item_id is not provided in config, we look it up via the binding
        if not item_id:
            wf_mgr = WorkflowStateManager("./automation-ideas")
            bindings = wf_mgr.get_bindings_for_run(run_id)
            if not bindings:
                return {"status": "error", "message": "No Kanban item bound to this run"}
            item_id = bindings[0]["item_id"]

        state_mgr = StateManager("./automation-ideas")
        
        if action == "move_item":
            new_stage = config.get("new_stage")
            if state_mgr.update_item(item_id, {"stage": new_stage}):
                return {"status": "success", "message": f"Moved {item_id} to {new_stage}"}
            return {"status": "error", "message": f"Failed to move {item_id}"}
            
        elif action == "add_comment":
            author = config.get("author", "Antikythera Engine")
            body = config.get("body", "")
            if state_mgr.add_comment(item_id, author, body):
                return {"status": "success", "message": f"Comment added to {item_id}"}
            return {"status": "error", "message": f"Failed to add comment to {item_id}"}
        
        return {"status": "error", "message": f"Unsupported action {action}"}

    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch is not applicable for internal adapter; raise to signal misuse."""
        raise NotImplementedError("InternalKanbanAdapter does not support fetch")

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        """Update is not applicable for internal adapter; raise to signal misuse."""
        raise NotImplementedError("InternalKanbanAdapter does not support update")

    async def create(self, payload: Dict[str, Any]) -> Any:
        """Create is not applicable for internal adapter; raise to signal misuse."""
        raise NotImplementedError("InternalKanbanAdapter does not support create")

    async def delete(self, resource_id: str) -> Any:
        """Delete is not applicable for internal adapter; raise to signal misuse."""
        raise NotImplementedError("InternalKanbanAdapter does not support delete")

    def check_status(self, run_id: str, config: Dict[str, Any]) -> str:
        # Internal actions are typically synchronous
        return "COMPLETED"
