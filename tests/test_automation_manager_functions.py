import os
import json
import pytest
from importlib import reload

def test_automation_manager_crud(tmp_path, monkeypatch):
    import agents.automation_manager as am_mod
    # Redirect registry dir to temporary location
    reg_dir = tmp_path / "registry"
    reg_file = reg_dir / "automation_registry.json"
    monkeypatch.setattr(am_mod, "REGISTRY_DIR", str(reg_dir))
    monkeypatch.setattr(am_mod, "REGISTRY_FILE", str(reg_file))
    # Reload to apply changes
    reload(am_mod)

    manager = am_mod.AutomationManager()
    # Initially empty
    assert manager.list_tasks() == {}

    task_id = "task1"
    meta = {"owner": "tester"}
    intent = {"action": "run"}
    policy = {"retries": 1}
    added = manager.add_task(task_id, meta, intent, policy)
    assert added is True
    assert task_id in manager.list_tasks()
    task = manager.get_task(task_id)
    assert task["metadata"]["owner"] == "tester"
    assert task["intent"] == intent

    # Update status
    updated = manager.update_task_status(task_id, "COMPLETED", outcome="success")
    assert updated is True
    task2 = manager.get_task(task_id)
    assert task2["metadata"]["status"] == "COMPLETED"
    assert task2["history"][0]["outcome"] == "success"

    # Get active tasks (none now because status not ACTIVE)
    assert manager.get_active_tasks() == []

    # Remove task
    removed = manager.remove_task(task_id)
    assert removed is True
    assert manager.get_task(task_id) is None
