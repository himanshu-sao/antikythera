from datetime import datetime
from typing import Dict, Any, Optional, List
from api.managers.base import BaseJSONManager

class BindingManager(BaseJSONManager):
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "workflow_bindings.json")

    def bind_run_to_item(self, run_id: str, item_id: str, binding_type: str = "PRIMARY") -> bool:
        try:
            bindings = self._load()
            binding_id = f"bind_{int(datetime.utcnow().timestamp() * 1000)}"
            bindings[binding_id] = {
                "run_id": run_id,
                "item_id": item_id.upper(),
                "binding_type": binding_type,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            self._save(bindings)
            return True
        except Exception:
            return False

    def get_bindings_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        bindings = self._load()
        return [b for b in bindings.values() if b["run_id"] == run_id]

    def get_run_id_for_item(self, item_id: str) -> Optional[str]:
        bindings = self._load()
        for b in bindings.values():
            if b["item_id"] == item_id.upper():
                return b["run_id"]
        return None
