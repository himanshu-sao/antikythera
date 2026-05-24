import json
import os
from typing import Any, Dict, Optional
from filelock import FileLock

class RunContext:
    """
    Persistent memory for a single workflow run.
    Allows steps to share data (e.g., a PR ID found in step 1 used in step 3).
    """
    def __init__(self, base_dir: str, run_id: str):
        self.base_dir = base_dir
        self.run_id = run_id
        self.context_path = os.path.join(base_dir, "run_contexts", f"{run_id}.json")
        self._lock = FileLock(self.context_path + ".lock")
        os.makedirs(os.path.dirname(self.context_path), exist_ok=True)

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.context_path):
            return {}
        try:
            with open(self.context_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, Any]):
        with open(self.context_path, "w") as f:
            json.dump(data, f, indent=2)

    def set(self, key: str, value: Any):
        """Set a value in the run context."""
        with self._lock:
            data = self._load()
            data[key] = value
            self._save(data)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the run context."""
        with self._lock:
            data = self._load()
            return data.get(key, default)

    def update(self, updates: Dict[str, Any]):
        """Batch update the run context."""
        with self._lock:
            data = self._load()
            data.update(updates)
            self._save(data)

    def get_all(self) -> Dict[str, Any]:
        """Return the full context."""
        with self._lock:
            return self._load()

    def clear(self):
        """Clear the run context."""
        with self._lock:
            if os.path.exists(self.context_path):
                os.remove(self.context_path)
