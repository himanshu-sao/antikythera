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

    def update_item_stage(self, item_id: str, new_stage: str) -> bool:
        state = self.load_state()
        items = state.get("items", {})
        
        if item_id not in items:
            return False
        
        items[item_id]["stage"] = new_stage
        items[item_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        self.save_state(state)
        return True

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        return state.get("items", {}).get(item_id)
