import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List

class StateManager:
    def __init__(self, state_path: str):
        self.state_path = state_path
        self._lock = threading.Lock()  # TODO-04/ENH-03: thread-safety lock

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path):
            return {"last_heartbeat": None, "items": {}}
        with open(self.state_path, "r") as f:
            return json.load(f)

    def save_state(self, state: Dict[str, Any]):
        # ENH-03: Atomic write via temp file + os.replace to prevent corruption on crash
        tmp_path = self.state_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, self.state_path)

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        item_id = item_id.upper()
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            if item_id not in items:
                return False
            items[item_id].update(updates)
            items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self.save_state(state)
            return True

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        item_id = item_id.upper()
        state = self.load_state()
        return state.get("items", {}).get(item_id)

    def create_item(self, item_id: str, title: str) -> bool:
        item_id = item_id.upper()
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            if item_id in items:
                return False
            intake_items = [item for item in items.values() if item.get("stage") == "INTAKE"]
            order = len(intake_items)
            items[item_id] = {
                "title": title,
                "stage": "INTAKE",
                            "priority": "medium",
            "confidence_score": 0,
            "description": "",
                "order": order,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "comments": [],
                "history": [{"stage": "INTAKE", "at": datetime.utcnow().isoformat() + "Z"}],
            }
            self.save_state(state)
            return True

    def delete_item(self, item_id: str) -> bool:
        # ENH-01: Delete item from state
        item_id = item_id.upper()
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            if item_id not in items:
                return False
            del items[item_id]
            self.save_state(state)
            return True

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        item_id = item_id.upper()
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            if item_id not in items:
                return None
            if "comments" not in items[item_id]:
                items[item_id]["comments"] = []
            comment = {
                "id": f"com_{int(datetime.utcnow().timestamp() * 1000)}",
                "author": author,
                "body": body,
                "createdAt": datetime.utcnow().isoformat() + "Z"
            }
            items[item_id]["comments"].append(comment)
            items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self.save_state(state)
            return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        # ENH-04: Delete a specific comment from an item
        item_id = item_id.upper()
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            if item_id not in items:
                return False
            comments = items[item_id].get("comments", [])
            original_len = len(comments)
            items[item_id]["comments"] = [c for c in comments if c.get("id") != comment_id]
            if len(items[item_id]["comments"]) == original_len:
                return False  # comment not found
            items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self.save_state(state)
            return True

    def reorder_items(self, stage: str, ordered_ids: List[str]) -> bool:
        # ENH-05: Bulk reorder items within a stage by updating their order field
        with self._lock:
            state = self.load_state()
            items = state.get("items", {})
            for index, item_id in enumerate(ordered_ids):
                uid = item_id.upper()
                if uid in items and items[uid].get("stage") == stage:
                    items[uid]["order"] = index
                    items[uid]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self.save_state(state)
            return True
