import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock

class StateManager:
    def __init__(self, state_path: str):
        self.state_path = state_path
        self.lock_path = state_path + ".lock"
        self._lock = FileLock(self.lock_path)

    def _get_default_state(self) -> Dict[str, Any]:
        return {
            "last_heartbeat": None,
            "items": {},
        }

    def load_state(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.state_path):
                return self._get_default_state()
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self._get_default_state()

    def save_state(self, state: Dict[str, Any]):
        with self._lock:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            tmp_path = self.state_path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, self.state_path)

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        item_id = item_id.upper()
        state = self.load_state()
        return state.get("items", {}).get(item_id)

    def create_item(self, item_id: str, title: str, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None) -> bool:
        item_id = item_id.upper()
        try:
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
                    "source_type": source_type,
                    "source_value": source_value,
                    "due_date": due_date,
                    "order": order,
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "comments": [],
                    "history": [{"stage": "INTAKE", "at": datetime.utcnow().isoformat() + "Z"}],
                }
                state["items"] = items
                self.save_state(state)
            return True
        except Exception:
            return False

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        item_id = item_id.upper()
        try:
            with self._lock:
                state = self.load_state()
                items = state.get("items", {})
                if item_id not in items:
                    return False
                
                items[item_id].update(updates)
                items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
                state["items"] = items
                self.save_state(state)
            return True
        except Exception:
            return False

    def delete_item(self, item_id: str) -> bool:
        item_id = item_id.upper()
        try:
            with self._lock:
                state = self.load_state()
                items = state.get("items", {})
                if item_id not in items:
                    return False
                del items[item_id]
                state["items"] = items
                self.save_state(state)
            return True
        except Exception:
            return False

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        item_id = item_id.upper()
        try:
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
                state["items"] = items
                self.save_state(state)
                return comment
        except Exception:
            return None

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        item_id = item_id.upper()
        try:
            with self._lock:
                state = self.load_state()
                items = state.get("items", {})
                if item_id not in items:
                    return False
                
                comments = items[item_id].get("comments", [])
                original_len = len(comments)
                items[item_id]["comments"] = [c for c in comments if c.get("id") != comment_id]
                
                if len(items[item_id]["comments"]) == original_len:
                    return False
                
                items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
                state["items"] = items
                self.save_state(state)
            return True
        except Exception:
            return False

    def reorder_items(self, stage: str, ordered_ids: List[str]) -> bool:
        try:
            with self._lock:
                state = self.load_state()
                items = state.get("items", {})

                stage_items = [id for id, item in items.items() if item.get("stage") == stage]

                for index, item_id in enumerate(ordered_ids):
                    uid = item_id.upper()
                    if uid in items and items[uid].get("stage") == stage:
                        items[uid]["order"] = index
                        items[uid]["updated_at"] = datetime.utcnow().isoformat() + "Z"

                current_max_order = len(ordered_ids) - 1 if ordered_ids else 0
                for uid in stage_items:
                    if uid not in [oid.upper() for oid in ordered_ids]:
                        items[uid]["order"] = current_max_order + 1
                        current_max_order += 1
                        items[uid]["updated_at"] = datetime.utcnow().isoformat() + "Z"

                state["items"] = items
                self.save_state(state)
            return True
        except Exception:
            return False
