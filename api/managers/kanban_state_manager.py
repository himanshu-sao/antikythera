import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock
from api.managers.base import BaseJSONManager
from api.managers._timestamps import sanitize_state

class KanbanStateManager(BaseJSONManager):
    """Manager for the legacy Kanban board state (pipeline-state.json)."""
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "pipeline-state.json")

    def load_state(self) -> Dict[str, Any]:
        with self.lock:
            if not os.path.exists(self.path):
                return {"items": {}, "stages": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]}
            try:
                with open(self.path, "r") as f:
                    state = json.load(f)
            except Exception:
                return {"items": {}}
        # P3.6: self-heal any non-ISO created_at (e.g. historical ``"now"``)
        # so stale fixtures and older writers don't leak to the UI/API.
        return sanitize_state(state)

    def create_item(self, item_id: str, title: str, goal: Optional[str] = None, description: Optional[str] = None, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None, complexity: Optional[str] = None) -> bool:
        with self.lock:
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
            self._save(state)
            return True

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        with self.lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            state["items"][normalized_id].update(updates)
            state["items"][normalized_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save(state)
            return True

    def delete_item(self, item_id: str) -> bool:
        with self.lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id in state["items"]:
                del state["items"][normalized_id]
                self._save(state)
                return True
            return False

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        return state["items"].get(item_id.upper())

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        with self.lock:
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
            self._save(state)
            return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        with self.lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            item = state["items"][normalized_id]
            initial_len = len(item["comments"])
            item["comments"] = [c for c in item["comments"] if c["id"] != comment_id]
            if len(item["comments"]) < initial_len:
                self._save(state)
                return True
            return False

    def reorder_items(self, stage: str, ordered_ids: List[str]):
        with self.lock:
            state = self.load_state()
            if "stages_order" not in state:
                state["stages_order"] = {}
            state["stages_order"][stage.upper()] = ordered_ids
            self._save(state)
