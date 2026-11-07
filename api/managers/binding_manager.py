from datetime import datetime
from typing import Dict, Any, Optional, List
from api.managers.base import BaseJSONManager, CorruptStateError

class BindingManager(BaseJSONManager):
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "workflow_bindings.json")

    def bind_run_to_item(self, run_id: str, item_id: str, binding_type: str = "PRIMARY") -> bool:
        def apply(bindings):
            # Millisecond timestamps can collide; never overwrite an existing binding.
            base_id = f"bind_{int(datetime.utcnow().timestamp() * 1000)}"
            binding_id, n = base_id, 1
            while binding_id in bindings:
                binding_id = f"{base_id}_{n}"
                n += 1
            bindings[binding_id] = {
                "run_id": run_id,
                "item_id": item_id.upper(),
                "binding_type": binding_type,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            return True, True

        try:
            return self._update(apply)
        except CorruptStateError:
            raise
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
