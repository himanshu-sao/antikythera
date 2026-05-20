import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

class StateManager:
    def __init__(self, state_path: str):
        self.state_path = state_path

    def load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_path):
            return {"last_heartbeat": None, "items": {}}
        with open(self.state_path, "r") as f:
            return json.load(f)

    def save_state(self, state: Dict[str, Any]):
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        item_id = item_id.upper()
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
        state = self.load_state()
        items = state.get("items", {})

        if item_id in items:
            return False

        # Calculate order based on current items in INTAKE
        intake_items = [item for item in items.values() if item.get("stage") == "INTAKE"]
        order = len(intake_items)

        items[item_id] = {
            "title": title,
            "stage": "INTAKE",
            "order": order,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        self.save_state(state)
        return True

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        item_id = item_id.upper()
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
