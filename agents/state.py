"""
Pipeline state management module.

Handles reading and writing of automation-ideas/pipeline-state.json,
the single source of truth for all pipeline state.
"""

import json
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, "automation-ideas", "pipeline-state.json")
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")


def _default_state():
    """Return a default pipeline state dict."""
    return {
        "last_heartbeat": None,
        "items": {},
    }


def load_state():
    """
    Load pipeline state from pipeline-state.json.

    Returns:
        dict: The pipeline state.

    Raises:
        FileNotFoundError: If the state file does not exist.
        json.JSONDecodeError: If the state file contains invalid JSON.
    """
    if not os.path.exists(STATE_FILE):
        return _default_state()
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    """
    Save pipeline state to pipeline-state.json.

    Args:
        state (dict): The pipeline state to persist.
    """
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_item(state, item_id):
    """
    Get a single pipeline item by ID.

    Args:
        state (dict): The pipeline state.
        item_id (str): The item ID (e.g. "ID-001").

    Returns:
        dict: The item data.

    Raises:
        KeyError: If the item ID does not exist.
    """
    if item_id not in state.get("items", {}):
        raise KeyError(f"Item {item_id} not found in pipeline state")
    return state["items"][item_id]


def update_item(state, item_id, updates):
    """
    Update fields on a pipeline item and set updated_at timestamp.

    Args:
        state (dict): The pipeline state.
        item_id (str): The item ID.
        updates (dict): Fields to update on the item.

    Raises:
        KeyError: If the item ID does not exist.
    """
    if item_id not in state.get("items", {}):
        raise KeyError(f"Item {item_id} not found in pipeline state")
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    state["items"][item_id].update(updates)
    state["items"][item_id]["updated_at"] = now


def add_history_entry(state, item_id, stage, agent=None):
    """
    Append a history entry to a pipeline item.

    Args:
        state (dict): The pipeline state.
        item_id (str): The item ID.
        stage (str): The stage name.
        agent (str, optional): The agent that performed the action.

    Raises:
        KeyError: If the item ID does not exist.
    """
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

    Args:
        state (dict): The pipeline state.

    Returns:
        str: The next ID (e.g. "ID-005").
    """
    items = state.get("items", {})
    max_num = 0
    for key in items:
        if key.startswith("ID-"):
            try:
                num = int(key.split("-")[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                continue
    next_num = max_num + 1
    return f"ID-{next_num:03d}"


def create_item_directory(item_id):
    """
    Create the requirements directory for a pipeline item.

    Args:
        item_id (str): The item ID (e.g. "ID-001").

    Returns:
        str: The path to the created directory.
    """
    dir_path = os.path.join(REQUIREMENTS_DIR, item_id)
    os.makedirs(dir_path, exist_ok=True)
    return dir_path