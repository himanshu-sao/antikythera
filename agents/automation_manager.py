import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

REGISTRY_DIR = os.path.abspath("registry")
REGISTRY_FILE = os.path.join(REGISTRY_DIR, "automation_registry.json")

class AutomationManager:
    def __init__(self):
        self._ensure_registry_exists()

    def _ensure_registry_exists(self):
        if not os.path.exists(REGISTRY_DIR):
            os.makedirs(REGISTRY_DIR)
        # Always start with a clean registry file
        with open(REGISTRY_FILE, "w") as f:
            json.dump({"tasks": {}}, f)

    def _load(self) -> Dict[str, Any]:
        try:
            with open(REGISTRY_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            return {"tasks": {}}

    def _save(self, data: Dict[str, Any]):
        try:
            with open(REGISTRY_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")

    def add_task(self, task_id: str, metadata: Dict[str, str], intent: Dict[str, str], execution_policy: Dict[str, Any]) -> bool:
        data = self._load()
        if task_id in data["tasks"]:
            logger.warning(f"Task {task_id} already exists.")
            return False

        new_task = {
            "metadata": {
                **metadata,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "status": "ACTIVE"
            },
            "intent": intent,
            "execution_policy": execution_policy,
            "history": []
        }

        data["tasks"][task_id] = new_task
        self._save(data)
        logger.info(f"Added task {task_id}")
        return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        data = self._load()
        return data["tasks"].get(task_id)

    def list_tasks(self) -> Dict[str, Any]:
        return self._load()["tasks"]

    def update_task_status(self, task_id: str, status: str, outcome: Optional[str] = None, log_ref: Optional[str] = None) -> bool:
        data = self._load()
        if task_id not in data["tasks"]:
            return False

        task = data["tasks"][task_id]
        task["metadata"]["status"] = status
        task["metadata"]["last_run"] = datetime.utcnow().isoformat() + "Z"

        if outcome or log_ref:
            history_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "outcome": outcome or "N/A"
            }
            if log_ref:
                history_entry["log_ref"] = log_ref
            task["history"].append(history_entry)

        self._save(data)
        return True

    def remove_task(self, task_id: str) -> bool:
        data = self._load()
        if task_id in data["tasks"]:
            del data["tasks"][task_id]
            self._save(data)
            return True
        return False

    def get_active_tasks(self) -> List[str]:
        data = self._load()
        return [tid for tid, task in data["tasks"].items() if task["metadata"]["status"] == "ACTIVE"]
