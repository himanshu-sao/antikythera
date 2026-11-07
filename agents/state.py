"""
Pipeline state management module.

Handles reading and writing of automation-ideas/pipeline-state.json,
the single source of truth for all pipeline state.
"""

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from filelock import FileLock

from api.managers._timestamps import sanitize_state
from api.managers.base import CorruptStateError

# Mode for a newly created state file (mkstemp creates 0600).
_DEFAULT_FILE_MODE = 0o644

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

def state_lock():
    """Return the shared (reentrant) state lock.

    Callers doing a read-modify-write (re-read, merge, save) hold this across
    the whole sequence. ``load_state``/``save_state`` take it reentrantly.
    """
    return _lock

def _find_identical_backup(path, data):
    directory = os.path.dirname(path) or "."
    prefix = os.path.basename(path) + ".corrupt-"
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return None
    for name in names:
        if not name.startswith(prefix):
            continue
        candidate = os.path.join(directory, name)
        try:
            with open(candidate, "rb") as f:
                if f.read() == data:
                    return candidate
        except OSError:
            continue
    return None


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _quarantine(path, bad_bytes, cause):
    """Copy unreadable state bytes to ``<path>.corrupt-<UTC stamp>`` and build the error.

    Mirrors ``BaseJSONManager._quarantine``: an identical existing backup is
    reused so a corrupt file hit every cycle is backed up once. The original
    file is never modified.
    """
    backup = _find_identical_backup(path, bad_bytes)
    if backup is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = f"{path}.corrupt-{stamp}"
        counter = 1
        while os.path.exists(backup):
            backup = f"{path}.corrupt-{stamp}-{counter}"
            counter += 1
        with open(backup, "wb") as f:
            f.write(bad_bytes)
    return CorruptStateError(path, backup, cause)


def load_state():
    """
    Load pipeline state from pipeline-state.json.

    A missing file returns the default state. A file that is not valid UTF-8
    JSON, or whose root is not an object, is backed up to
    ``<file>.corrupt-<UTC timestamp>`` (once; identical bytes reuse the backup),
    left untouched, and reported with ``CorruptStateError``.
    """
    with _lock:
        if not os.path.exists(STATE_FILE):
            return _default_state()
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
        except ValueError as exc:  # JSONDecodeError and UnicodeDecodeError both subclass ValueError
            raise _quarantine(STATE_FILE, _read_bytes(STATE_FILE), exc) from exc
        if not isinstance(state, dict):
            raise _quarantine(
                STATE_FILE,
                _read_bytes(STATE_FILE),
                ValueError(f"root is {type(state).__name__}, expected an object"),
            )
    # P3.6: self-heal non-ISO created_at on read (see api/managers/_timestamps.py).
    return sanitize_state(state)

def save_state(state):
    """Save pipeline state to the JSON file atomically.

    2.10 / T12: the payload is written to a temp file in the same directory,
    flushed and fsynced, then moved over ``STATE_FILE`` with ``os.replace``.
    A failure part-way through (e.g. ``json.dump`` raising) leaves the previous
    file intact and removes the temp file. The write runs under the same
    ``_lock`` / lock file as before.
    """
    with _lock:
        target_dir = os.path.dirname(STATE_FILE)
        os.makedirs(target_dir, exist_ok=True)
        try:
            mode = stat.S_IMODE(os.stat(STATE_FILE).st_mode)
        except OSError:
            mode = _DEFAULT_FILE_MODE
        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(STATE_FILE) + ".", suffix=".tmp", dir=target_dir
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            # mkstemp creates 0600; keep the previous file's mode (R23).
            os.chmod(tmp_path, mode)
            os.replace(tmp_path, STATE_FILE)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

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
