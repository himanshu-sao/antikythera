import os
import pytest
from importlib import reload

def test_state_crud(tmp_path, monkeypatch):
    import agents.state as state_mod
    # Override STATE_FILE and LOCK_FILE to temporary locations
    state_file = tmp_path / "pipeline-state.json"
    lock_file = tmp_path / "pipeline-state.json.lock"
    monkeypatch.setattr(state_mod, "STATE_FILE", str(state_file))
    monkeypatch.setattr(state_mod, "LOCK_FILE", str(lock_file))
    # reload to recreate the FileLock with new path
    reload(state_mod)

    # Start with default state, then save and load
    default = state_mod._default_state()
    state_mod.save_state(default)
    loaded = state_mod.load_state()
    assert loaded == default

    # Add a sample item
    item_id = "ID-001"
    loaded["items"][item_id] = {"name": "test", "created_at": "now"}
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
