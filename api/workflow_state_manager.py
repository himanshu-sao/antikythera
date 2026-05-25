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
        self.state_path = os.path.join(base_dir, "pipeline-state.json")
        self.events_dir = os.path.join(base_dir, "events")
        
        # Locks for each file
        self._templates_lock = FileLock(self.templates_path + ".lock")
        self._runs_lock = FileLock(self.runs_path + ".lock")
        self._bindings_lock = FileLock(self.bindings_path + ".lock")
        self._state_lock = FileLock(self.state_path + ".lock")

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

    def load_state(self) -> Dict[str, Any]:
        """Returns the legacy Kanban board state."""
        with self._state_lock:
            if not os.path.exists(self.state_path):
                return {"items": {}, "stages": ["INTAKE", "REFINEMENT", "REVIEW_SPEC", "ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED", "EXECUTING", "DONE"]}
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except Exception:
                return {"items": {}}

    def create_item(self, item_id: str, title: str, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None) -> bool:
        with self._state_lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id in state["items"]:
                return False
            state["items"][normalized_id] = {
                "title": title,
                "stage": "INTAKE",
                "priority": "medium",
                "source_type": source_type,
                "source_value": source_value,
                "due_date": due_date,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "comments": []
            }
            self._save_json(self.state_path, self._state_lock, state)
            return True

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        with self._state_lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            state["items"][normalized_id].update(updates)
            state["items"][normalized_id]["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._save_json(self.state_path, self._state_lock, state)
            return True

    def delete_item(self, item_id: str) -> bool:
        with self._state_lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id in state["items"]:
                del state["items"][normalized_id]
                self._save_json(self.state_path, self._state_lock, state)
                return True
            return False

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        state = self.load_state()
        return state["items"].get(item_id.upper())

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        with self._state_lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return None
            comment = {
                "id": f"com_{int(datetime.utcnow().timestamp() * 1000)}",
                "author": author,
                "body": body,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }
            state["items"][normalized_id]["comments"].append(comment)
            self._save_json(self.state_path, self._state_lock, state)
            return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        with self._state_lock:
            state = self.load_state()
            normalized_id = item_id.upper()
            if normalized_id not in state["items"]:
                return False
            item = state["items"][normalized_id]
            initial_len = len(item["comments"])
            item["comments"] = [c for c in item["comments"] if c["id"] != comment_id]
            if len(item["comments"]) < initial_len:
                self._save_json(self.state_path, self._state_lock, state)
                return True
            return False

    def reorder_items(self, stage: str, ordered_ids: List[str]):
        """
        Persists the order of items within a specific stage.
        Since pipeline-state.json doesn't have a top-level 'order' field,
        we store the order as a list of IDs under the state['stages_order'][stage] key.
        """
        with self._state_lock:
            state = self.load_state()
            if "stages_order" not in state:
                state["stages_order"] = {}
            
            state["stages_order"][stage.upper()] = ordered_ids
            self._save_json(self.state_path, self._state_lock, state)

    def delete_template(self, template_id: str) -> bool:
        try:
            templates = self._load_json(self.templates_path, self._templates_lock)
            if template_id not in templates:
                return False
            del templates[template_id]
            self._save_json(self.templates_path, self._templates_lock, templates)
            return True
        except Exception:
            return False

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
