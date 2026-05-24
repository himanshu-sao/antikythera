import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock

class StateManager:
    """
    The legacy StateManager for the general Kanban board.
    Now integrated with WorkflowStateManager to avoid state duplication.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.state_path = os.path.join(base_dir, "pipeline-state.json")
        self._lock = FileLock(self.state_path + ".lock")

    def load_state(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.state_path):
                return {"items": {}, "stages": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]}
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {"items": {}}

    def create_item(self, item_id: str, title: str, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None) -> bool:
        with self._lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id in state["items"]:
                return False
            state["items"][normalized_id] = {
                "title": title,
                "stage": "INTAKE",
                "priority": "medium",
                "source_type": source_type,
                "source_value": source_value,
                "due_date": due_date,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "comments": []
            }
            with open(self.state_path, "w") as f:
                json.dump(state, f, indent=2)
            return True

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        with self._lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            state["items"][normalized_id].update(updates)
            state["items"][normalized_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            with open(self.state_path, "w") as f:
                json.dump(state, f, indent=2)
            return True

    def delete_item(self, item_id: str) -> bool:
        with self._lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id in state["items"]:
                del state["items"][normalized_id]
                with open(self.state_path, "w") as f:
                    json.dump(state, f, indent=2)
                return True
            return False

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        return state["items"].get(item_id.upper())

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return None
            comment = {
                "id": f"com_{int(datetime.utcnow().timestamp() * 1000)}",
                "author": author,
                "body": body,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            state["items"][normalized_id]["comments"].append(comment)
            with open(self.state_path, "w") as f:
                json.dump(state, f, indent=2)
            return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        with self._lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            item = state["items"][normalized_id]
            initial_len = len(item["comments"])
            item["comments"] = [c for c in item["comments"] if c["id"] != comment_id]
            if len(item["comments"]) < initial_len:
                with open(self.state_path, "w") as f:
                    json.dump(state, f, indent=2)
                return True
            return False

    def reorder_items(self, stage: str, ordered_ids: List[str]):
        with self._lock:
            state = self.load_state()
            stage_upper = stage.upper()
            # This is a simplified reorder that just updates a sort key if it existed.
            # Since we don't store explicit order in the state currently, we'll just log it.
            pass
