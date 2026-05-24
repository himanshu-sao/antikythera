import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from filelock import FileLock

class WorkflowStateManager:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.templates_path = os.path.join(base_dir, "workflow_templates.json")
        self.runs_path = os.path.join(base_dir, "workflow_runs.json")
        self.bindings_path = os.path.join(base_dir, "workflow_bindings.json")
        self.events_dir = os.path.join(base_dir, "events")
        
        # Locks for each file
        self._templates_lock = FileLock(self.templates_path + ".lock")
        self._runs_lock = FileLock(self.runs_path + ".lock")
        self._bindings_lock = FileLock(self.bindings_path + ".lock")

    def _load_json(self, path: str, lock: Any) -> Dict[str, Any]:
        with lock:
            if not os.path.exists(path):
                return {}
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_json(self, path: str, lock: Any, data: Dict[str, Any]):
        with lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, path)

    # --- Template Management ---

    def save_template(self, template_id: str, template_data: Dict[str, Any]) -> bool:
        try:
            templates = self._load_json(self.templates_path, self._templates_lock)
            template_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if "created_at" not in template_data:
                template_data["created_at"] = datetime.utcnow().isoformat() + "Z"
            
            templates[template_id] = template_data
            self._save_json(self.templates_path, self._templates_lock, templates)
            return True
        except Exception:
            return False

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        templates = self._load_json(self.templates_path, self._templates_lock)
        return templates.get(template_id)

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = self._load_json(self.templates_path, self._templates_lock)
        return [{"template_id": tid, **data} for tid, data in templates.items()]

    # --- Run Management ---

    def create_run(self, run_id: str, run_data: Dict[str, Any]) -> bool:
        try:
            runs = self._load_json(self.runs_path, self._runs_lock)
            run_data["started_at"] = datetime.utcnow().isoformat() + "Z"
            runs[run_id] = run_data
            self._save_json(self.runs_path, self._runs_lock, runs)
            return True
        except Exception:
            return False

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        try:
            runs = self._load_json(self.runs_path, self._runs_lock)
            if run_id not in runs:
                return False
            runs[run_id].update(updates)
            self._save_json(self.runs_path, self._runs_lock, runs)
            return True
        except Exception:
            return False

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        runs = self._load_json(self.runs_path, self._runs_lock)
        return runs.get(run_id)

    # --- Event Logging (The Timeline) ---

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

    # --- Binding Management ---

    def bind_run_to_item(self, run_id: str, item_id: str, binding_type: str = "PRIMARY") -> bool:
        try:
            bindings = self._load_json(self.bindings_path, self._bindings_lock)
            binding_id = f"bind_{int(datetime.utcnow().timestamp() * 1000)}"
            bindings[binding_id] = {
                "run_id": run_id,
                "item_id": item_id.upper(),
                "binding_type": binding_type,
                "created_at": datetime.utcnow().isoformat() + "Z"
            }
            self._save_json(self.bindings_path, self._bindings_lock, bindings)
            return True
        except Exception:
            return False

    def get_bindings_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        bindings = self._load_json(self.bindings_path, self._bindings_lock)
        return [b for b in bindings.values() if b["run_id"] == run_id]

    def get_run_id_for_item(self, item_id: str) -> Optional[str]:
        bindings = self._load_json(self.bindings_path, self._bindings_lock)
        for b in bindings.values():
            if b["item_id"] == item_id.upper():
                return b["run_id"]
        return None
