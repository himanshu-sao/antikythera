import json
import os
import pytest

from agents import state as state_mod
from filelock import FileLock


def test_state_crud(tmp_path, monkeypatch):
    """Exercise agents.state helpers with an isolated temporary state file.

    P3.6 NOTE: ``save_state`` / ``load_state`` read/write ``STATE_FILE``
    directly, so we monkeypatch those module-level constants *and* the
    FileLock imported at module scope. We do NOT use ``reload()`` because
    it re-executes the ``from api.managers._timestamps import sanitize_state``
    import, which drags in api managers that may already have a reference
    to the live ``pipeline-state.json`` path — causing writes to leak to
    the real file when the full test suite runs.
    """
    state_file = tmp_path / "pipeline-state.json"
    lock_file = tmp_path / "pipeline-state.json.lock"

    monkeypatch.setattr(state_mod, "STATE_FILE", str(state_file))
    monkeypatch.setattr(state_mod, "LOCK_FILE", str(lock_file))
    monkeypatch.setattr(state_mod, "_lock", FileLock(str(lock_file)))

    # Start with default state, then save and load
    default = state_mod._default_state()
    state_mod.save_state(default)
    loaded = state_mod.load_state()
    assert loaded == default

    # Add a sample item — use a real ISO timestamp, not "now"
    item_id = "ID-001"
    loaded["items"][item_id] = {
        "name": "test",
        "created_at": "2026-07-13T19:40:12.464956Z",
    }
    state_mod.save_state(loaded)
    reloaded = state_mod.load_state()
    assert reloaded["items"][item_id]["name"] == "test"

    # Update item and verify timestamp key added
    state_mod.update_item(reloaded, item_id, {"status": "active"})
    assert reloaded["items"][item_id]["status"] == "active"
    assert "updated_at" in reloaded["items"][item_id]

    # Add history entry
    state_mod.add_history_entry(reloaded, item_id, "INIT", agent="tester")
    history = reloaded["items"][item_id]["history"]
    assert isinstance(history, list) and history[0]["stage"] == "INIT"
    assert history[0]["agent"] == "tester"

    # Verify next ID generation
    next_id = state_mod.get_next_id(reloaded)
    assert next_id == "ID-002"

    # Create item directory and ensure it exists
    dir_path = state_mod.create_item_directory(item_id)
    assert os.path.isdir(dir_path)
