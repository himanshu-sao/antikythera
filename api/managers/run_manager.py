import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock
from api.managers.base import BaseJSONManager

class RunManager(BaseJSONManager):
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "workflow_runs.json")
        self.events_dir = os.path.join(base_dir, "events")

    def create_run(self, run_id: str, run_data: Dict[str, Any]) -> bool:
        try:
            runs = self._load()
            run_data["started_at"] = datetime.utcnow().isoformat() + "Z"
            runs[run_id] = run_data
            self._save(runs)
            return True
        except Exception:
            return False

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        try:
            runs = self._load()
            if run_id not in runs:
                return False
            runs[run_id].update(updates)
            self._save(runs)
            return True
        except Exception:
            return False

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        runs = self._load()
        return runs.get(run_id)

    def log_event(self, run_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system") -> bool:
        try:
            run_events_path = os.path.join(self.events_dir, f"{run_id}.jsonl")
            os.makedirs(self.events_dir, exist_ok=True)
            
            event = {
                "event_id": f"ev_{int(datetime.utcnow().timestamp() * 1000)}",
                "run_id": run_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": event_type,
                "payload": payload,
                "actor": actor
            }
            
            with open(run_events_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            return True
        except Exception:
            return False

    def get_run_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        run_events_path = os.path.join(self.events_dir, f"{run_id}.jsonl")
        if not os.path.exists(run_events_path):
            return []
        
        events = []
        try:
            with open(run_events_path, "r") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        except Exception:
            pass
        return events
