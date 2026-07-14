import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock

from api.managers._timestamps import sanitize_state

class StateManager:
    """
    The legacy StateManager for the general Kanban board.
    Now integrated with WorkflowStateManager to avoid state duplication.
    """
    def __init__(self, base_dir: str):
        """Initialize StateManager.

        ``base_dir`` may be a directory containing ``pipeline-state.json``
        or a direct path to the ``pipeline-state.json`` file. The constructor
        normalises the path so that ``self.state_path`` always points to the JSON
        file and ``self._lock`` is created alongside it.
        """
        # Determine if ``base_dir`` is already a file path
        if base_dir.endswith('.json'):
            self.state_path = base_dir
            self.base_dir = os.path.dirname(base_dir)
        else:
            self.base_dir = base_dir
            self.state_path = os.path.join(base_dir, "pipeline-state.json")
        # Use a lock file alongside the state file
        self._lock = FileLock(os.path.join(os.path.dirname(self.state_path), ".state.lock"))

    def load_state(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.state_path):
                return {"items": {}, "stages": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]}
            try:
                with open(self.state_path, "r") as f:
                    state = json.load(f)
            except Exception:
                return {"items": {}}
        # P3.6: self-heal non-ISO created_at on read (see api/managers/_timestamps.py).
        return sanitize_state(state)

    def _save_json(self, state: Dict[str, Any]):
        # Atomic write: temp file + rename
        with self._lock:
            tmp_path = self.state_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, self.state_path)

    def create_item(self, item_id: str, title: str, goal: Optional[str] = None, description: Optional[str] = None, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None, complexity: Optional[str] = None) -> bool:
        state = self.load_state()
        normalized_id = item_id.upper()
        if normalized_id in state["items"]:
            return False
        state["items"][normalized_id] = {
            "title": title,
            "goal": goal,
            "description": description,
            "stage": "INTAKE",
            "priority": "medium",
            "complexity": complexity,
            "source_type": source_type,
            "source_value": source_value,
            "due_date": due_date,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "comments": []
        }
        self._save_json(state)
        return True

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        state = self.load_state()
        normalized_id = item_id.upper()
        if normalized_id not in state["items"]:
            return False
        state["items"][normalized_id].update(updates)
        state["items"][normalized_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._save_json(state)
        return True

    def delete_item(self, item_id: str) -> bool:
        state = self.load_state()
        normalized_id = item_id.upper()
        if normalized_id in state["items"]:
            del state["items"][normalized_id]
            self._save_json(state)
            return True
        return False

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        return state["items"].get(item_id.upper())

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
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
        self._save_json(state)
        return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        state = self.load_state()
        normalized_id = item_id.upper()
        if normalized_id not in state["items"]:
            return False
        item = state["items"][normalized_id]
        initial_len = len(item["comments"])
        item["comments"] = [c for c in item["comments"] if c["id"] != comment_id]
        if len(item["comments"]) < initial_len:
            self._save_json(state)
            return True
        return False

    def reorder_items(self, stage: str, ordered_ids: List[str]):
        """
        Persists the order of items within a specific stage.
        """
        with self._lock:
            state = self.load_state()
            if "stages_order" not in state:
                state["stages_order"] = {}
            
            state["stages_order"][stage.upper()] = ordered_ids
            self._save_json(state)
