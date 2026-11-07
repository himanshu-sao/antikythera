"""The autouse ``isolate_data_dir`` fixture is the single isolation point.

Every holder of workflow state must point at the same WorkflowStateManager,
rooted under the per-test tmp_path, so no test can touch the real
automation-ideas/ directory.
"""
import os

import pytest

import api.main as api_main
from api.workflow_state_manager import WorkflowStateManager


def _under(path, root):
    return os.path.abspath(str(path)).startswith(os.path.abspath(str(root)) + os.sep)


@pytest.fixture
def sm():
    return api_main.state_manager


def test_fixture_yields_base_under_tmp(isolate_data_dir, tmp_path):
    assert isolate_data_dir == tmp_path / "automation-ideas"
    assert (isolate_data_dir / "knowledge" / "deltas").is_dir()
    for name in ("user.md", "skills.md", "memory.md"):
        assert (isolate_data_dir / "knowledge" / name).is_file()


def test_module_state_manager_is_tmp(isolate_data_dir, sm):
    assert isinstance(sm, WorkflowStateManager)
    assert sm.base_dir == str(isolate_data_dir)
    assert api_main.get_state_manager() is sm


def test_state_manager_sub_managers_under_tmp(isolate_data_dir, sm):
    assert _under(sm.runs.path, isolate_data_dir)
    assert _under(sm.brain.knowledge_dir, isolate_data_dir)


def test_app_state_holder_is_same_manager(sm):
    assert api_main.app.state.state_manager is sm


def test_engine_holders_point_at_tmp_manager(isolate_data_dir, sm):
    assert api_main.engine.state_manager is sm
    assert api_main.engine.run_manager is sm.runs
    assert _under(api_main.engine.run_manager.path, isolate_data_dir)


def test_escalator_and_retry_manager_point_at_tmp_manager(sm):
    assert api_main.escalator.state_manager is sm
    assert api_main.retry_manager.state_manager is sm


def test_scheduler_points_at_tmp_manager(sm):
    assert api_main.scheduler.state_manager is sm


def test_hub_holders_point_at_tmp(isolate_data_dir):
    assert api_main.app.state.hub is api_main.hub
    assert api_main.engine.hub is api_main.hub
    assert api_main.scheduler.hub is api_main.hub
    assert os.path.abspath(api_main.hub.base_dir) == os.path.abspath(str(isolate_data_dir))
    assert _under(api_main.hub.config_path, isolate_data_dir)


def test_run_written_via_engine_run_manager_lands_in_tmp(isolate_data_dir):
    api_main.engine.run_manager.create_run("run_iso", {"status": "RUNNING", "template_id": "T"})
    assert api_main.get_state_manager().runs.get_run("run_iso")["template_id"] == "T"
    assert os.path.isfile(api_main.engine.run_manager.path)
    assert _under(api_main.engine.run_manager.path, isolate_data_dir)


def test_retry_and_escalator_share_writes_with_state_manager(sm):
    sm.runs.create_run("run_retry", {"status": "RUNNING", "template_id": "T"})
    # RetryManager reads runs through state_manager; it must see the tmp run.
    assert api_main.retry_manager.state_manager.get_run("run_retry")["template_id"] == "T"


def test_test_may_swap_state_manager_itself(monkeypatch, isolate_data_dir):
    """Tests such as test_api.py swap api.main.state_manager; that must still work."""
    sentinel = object()
    monkeypatch.setattr(api_main, "state_manager", sentinel)
    assert api_main.get_state_manager() is sentinel


def test_no_separate_reset_fixture(request):
    """Merged: only isolate_data_dir remains as the isolation fixture."""
    assert "reset_state_manager" not in request.fixturenames
    assert "isolate_data_dir" in request.fixturenames


def test_each_test_gets_its_own_tmp_manager(tmp_path):
    # The manager must be rooted at this test's tmp_path, not a previous test's.
    assert _under(api_main.state_manager.base_dir, tmp_path)
