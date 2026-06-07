import os
import json
from typing import Dict, Any
from filelock import FileLock

class BaseJSONManager:
    """Base class for managers that handle JSON file persistence with locking."""
    def __init__(self, base_dir: str, filename: str):
        self.base_dir = base_dir
        self.path = os.path.join(base_dir, filename)
        self.lock = FileLock(self.path + ".lock")

    def _load(self) -> Dict[str, Any]:
        with self.lock:
            if not os.path.exists(self.path):
                return {}
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save(self, data: Dict[str, Any]):
        with self.lock:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, self.path)
