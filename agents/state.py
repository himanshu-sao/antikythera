"""
Pipeline state management module.

Handles reading and writing of automation-ideas/pipeline-state.json,
the single source of truth for all pipeline state.
"""

import json
import os
from datetime import datetime
from filelock import FileLock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, "automation-ideas", "pipeline-state.json")
LOCK_FILE = STATE_FILE + ".lock"
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")

# Global lock for cross-process state access
_lock = FileLock(LOCK_FILE)

def _default_state():
    """Return a default pipeline state dict."""
    return {
        "last_heartbeat": None,
        "items": {},
    }

def load_state():
    """
    Load pipeline state from pipeline-state.json.
    """
    with _lock:
        if not os.path.exists(STATE_FILE):
            return _default_state()
        with open(STATE_FILE, "r") as f:
            return json.load(f)

def save_state(state):
    """Save pipeline state to the JSON file.
    The implementation writes directly to ``STATE_FILE`` under a lock.
    This avoids double‑writes that broke the ``test_save_state_writes_json`` test.
    """
    with _lock:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

def get_item(state, item_id):
    """
    Get a single pipeline item by ID.
    """
    item_id = item_id.upper()
    if item_id not in state.get("items", {}):
        raise KeyError(f"Item {item_id} not found in pipeline state")
    return state["items"][item_id]

def update_item(state, item_id, updates):
    """
    Update fields on a pipeline item and set updated_at timestamp.
    Note: This function expects the state to be managed by the caller's lock.
    """
    item_id = item_id.upper()
    if item_id not in state.get("items", {}):
        raise KeyError(f"Item {item_id} not found in pipeline state")
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    state["items"][item_id].update(updates)
    state["items"][item_id]["updated_at"] = now

def add_history_entry(state, item_id, stage, agent=None):
    """
    Append a history entry to a pipeline item.
    """
    item_id = item_id.upper()
    if item_id not in state.get("items", {}):
        raise KeyError(f"Item {item_id} not found in pipeline state")
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {"stage": stage, "at": now}
    if agent:
        entry["agent"] = agent
    state["items"][item_id].setdefault("history", []).append(entry)

def get_next_id(state):
    """
    Auto-increment the next available ID based on existing items.
    """
    items = state.get("items", {})
    max_num = 0
    for key in items:
        upper_key = key.upper()
        if upper_key.startswith("ID-"):
            try:
                num = int(upper_key.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                continue
    next_num = max_num + 1
    return f"ID-{next_num:03d}"

def create_item_directory(item_id):
    """
    Create the requirements directory for a pipeline item.
    """
    item_id = item_id.upper()
    dir_path = os.path.join(REQUIREMENTS_DIR, item_id)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path
