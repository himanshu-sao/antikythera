import json

import pytest


@pytest.fixture
def registry_paths(tmp_path, monkeypatch):
    """Redirect the registry to tmp. The functions read REGISTRY_DIR and
    REGISTRY_FILE at call time, so monkeypatching is enough (no reload)."""
    import agents.automation_manager as am_mod

    reg_dir = tmp_path / "registry"
    reg_file = reg_dir / "automation_registry.json"
    monkeypatch.setattr(am_mod, "REGISTRY_DIR", str(reg_dir))
    monkeypatch.setattr(am_mod, "REGISTRY_FILE", str(reg_file))
    return reg_dir, reg_file


def test_automation_manager_crud(registry_paths):
    import agents.automation_manager as am_mod

    reg_dir, reg_file = registry_paths
    manager = am_mod.AutomationManager()
    # Initially empty
    assert manager.list_tasks() == {}
    assert reg_file.is_file()

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


def test_registry_writes_stay_in_tmp(registry_paths):
    import agents.automation_manager as am_mod

    _, reg_file = registry_paths
    manager = am_mod.AutomationManager()
    manager.add_task("task-tmp", {"owner": "t"}, {"action": "run"}, {})
    data = json.loads(reg_file.read_text())
    assert "task-tmp" in data["tasks"]
    assert am_mod.REGISTRY_FILE == str(reg_file)
