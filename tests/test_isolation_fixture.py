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


# ----------------------------------------------------------------------
# P4-1: module-level data paths outside the state managers
# ----------------------------------------------------------------------
def test_handlers_data_dir_is_tmp(isolate_data_dir):
    import agents.handlers as agent_handlers
    assert os.path.abspath(agent_handlers.DATA_DIR) == os.path.abspath(str(isolate_data_dir))


def test_brain_loop_paths_are_tmp(isolate_data_dir):
    import agents.brain_loop as brain_loop
    assert _under(brain_loop.BRAIN_DIR, isolate_data_dir)
    assert _under(brain_loop.PATTERNS_FILE, isolate_data_dir)
    assert _under(brain_loop.PENDING_UPDATES_FILE, isolate_data_dir)
    assert _under(brain_loop.HISTORY_DIR, isolate_data_dir)
    assert os.path.basename(brain_loop.PATTERNS_FILE) == "patterns.md"
    assert os.path.basename(brain_loop.PENDING_UPDATES_FILE) == "pending-updates.md"
    assert os.path.basename(brain_loop.HISTORY_DIR) == "history"


def test_brain_loop_apply_writes_only_under_tmp(isolate_data_dir):
    import agents.brain_loop as brain_loop
    os.makedirs(brain_loop.BRAIN_DIR, exist_ok=True)
    with open(brain_loop.PENDING_UPDATES_FILE, "w") as f:
        f.write("**review_status:** APPROVED\n**What to add:** iso-check\n")
    with open(brain_loop.PATTERNS_FILE, "w") as f:
        f.write("# Patterns\n")
    brain_loop.apply_approved_updates()
    assert "iso-check" in open(brain_loop.PATTERNS_FILE).read()


def test_executor_requirements_root_is_redirected(isolate_data_dir):
    import agents.executor_tools as executor_tools
    from agents.executor import item_requirements_dir as exec_item_dir
    assert executor_tools.REQUIREMENTS_ROOT == str(isolate_data_dir / "requirements")
    assert _under(executor_tools.requirements_root(), isolate_data_dir)
    assert _under(exec_item_dir("ID-ISO-1"), isolate_data_dir)


def test_executor_resolves_relative_paths_under_tmp_requirements(isolate_data_dir):
    import agents.executor_tools as executor_tools
    resolved = executor_tools._resolve_item_path("out.txt", "ID-ISO-2")
    assert _under(resolved, isolate_data_dir)
    assert resolved == os.path.join(str(isolate_data_dir), "requirements", "ID-ISO-2", "out.txt")


def test_executor_default_derives_from_cwd_when_unpatched(monkeypatch, tmp_path):
    """Without the fixture's redirect the historical cwd-relative layout holds."""
    import agents.executor_tools as executor_tools
    monkeypatch.setattr(executor_tools, "REQUIREMENTS_ROOT", None)
    monkeypatch.chdir(str(tmp_path))
    expected = os.path.join(os.getcwd(), "automation-ideas", "requirements")
    assert executor_tools.requirements_root() == expected
    assert executor_tools.item_requirements_dir("ID-D") == os.path.join(expected, "ID-D")


def test_executor_report_path_follows_redirect(monkeypatch, isolate_data_dir):
    """_finalize_phase writes execution_report.md under the redirected root."""
    from agents.executor import ExecutorAgent
    agent = ExecutorAgent.__new__(ExecutorAgent)
    agent.implementation_log = ["did a thing"]
    agent.run_manager = None
    agent.run_id = "run"
    agent._log_progress = lambda *_a, **_k: None
    agent._finalize_phase("ID-REPORT")
    report = isolate_data_dir / "requirements" / "ID-REPORT" / "execution_report.md"
    assert report.is_file()


# ----------------------------------------------------------------------
# P4-2: logger resolves its default directory at call time
# ----------------------------------------------------------------------
def test_default_log_dir_is_redirected(isolate_data_dir):
    import agents.logger as agent_logger
    assert _under(agent_logger.DEFAULT_LOG_DIR, isolate_data_dir)


def test_logger_created_before_fixture_still_writes_under_tmp(isolate_data_dir):
    """A logger built on the real default path earlier must not be handed back.

    TaskLogger does not touch the disk until a write, so constructing one on the
    real relative default here is safe; the assertion is about where a later
    get_logger() call writes.
    """
    import agents.logger as agent_logger
    earlier = agent_logger.TaskLogger("ID-EARLY", "automation-ideas/logs")
    later = agent_logger.get_logger("ID-EARLY")
    assert later is not earlier
    assert _under(later.log_dir, isolate_data_dir)
    later.info("tester", "START", "hello")
    assert (isolate_data_dir / "logs" / "ID-EARLY" / "timeline.jsonl").is_file()
    assert later.get_logs()[0]["message"] == "hello"


def test_get_logger_cache_is_keyed_by_directory(isolate_data_dir, tmp_path):
    import agents.logger as agent_logger
    other = tmp_path / "elsewhere"
    explicit = agent_logger.TaskLogger("ID-KEY", str(other))
    default = agent_logger.get_logger("ID-KEY")
    assert default is not explicit
    assert default.log_dir != explicit.log_dir
    assert agent_logger.get_logger("id-key") is default


def test_fixture_redirects_timeline_logs_end_to_end(isolate_data_dir):
    import api.utils as api_utils
    from agents import logger as task_logger
    assert _under(api_utils.LOG_BASE_DIR, isolate_data_dir)
    task_logger.get_logger("ID-TL").info("orchestrator", "PING", "pong")
    expected = isolate_data_dir / "logs" / "ID-TL" / "timeline.jsonl"
    assert expected.is_file()


# ----------------------------------------------------------------------
# P1-10: provider env, project .env and AI engine config are isolated
# ----------------------------------------------------------------------
_CREDS = (
    "GOOGLE_API_KEY", "GOOGLE_API_KEY_KANBAN", "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_AUTH_TOKEN",
    "JIRA_PAT", "JIRA_TOKEN", "GITHUB_TOKEN", "IBM_BOB_SHELL_DEFAULT_KEY",
)


def test_credential_env_vars_are_absent_inside_tests():
    for name in _CREDS:
        assert name not in os.environ, f"{name} leaked into a test"


def test_credential_env_vars_removed_then_restored_by_monkeypatch(monkeypatch):
    """Values set by one test are rolled back by monkeypatch, so the next starts clean."""
    for name in _CREDS:
        monkeypatch.setenv(name, "placeholder")
    assert all(os.environ.get(n) == "placeholder" for n in _CREDS)


def test_llm_client_load_dotenv_is_stubbed(monkeypatch, tmp_path):
    import dotenv
    import agents.llm_client as llm_client
    assert llm_client.load_dotenv is not dotenv.load_dotenv
    monkeypatch.chdir(str(tmp_path))
    (tmp_path / ".env").write_text("ISO_SHOULD_NOT_LOAD=1\n")
    assert llm_client.load_dotenv() is False
    assert "ISO_SHOULD_NOT_LOAD" not in os.environ


def test_llm_client_construction_does_not_read_dotenv(monkeypatch, tmp_path):
    import agents.llm_client as llm_client
    monkeypatch.chdir(str(tmp_path))
    (tmp_path / ".env").write_text("ISO_DOTENV_MARKER=should-not-load\n")
    cfg = tmp_path / "config.yaml"
    cfg.write_text("llm:\n  provider: mock\n  model: mock\n")
    monkeypatch.setattr(llm_client, "_resolve_from_config_service", lambda: None)
    monkeypatch.setattr(llm_client.LLMClient, "_initialize_client", lambda self: None)
    llm_client.LLMClient(config_path=str(cfg))
    assert "ISO_DOTENV_MARKER" not in os.environ


def test_ai_engine_config_singleton_is_on_tmp_home(isolate_provider_env, isolate_data_dir):
    import api.services.ai_engine_config as aec
    svc = aec.get_ai_engine_config()
    assert svc is isolate_provider_env
    assert _under(svc.config_path, isolate_data_dir.parent)
    assert _under(svc._persistent_env_path(), isolate_data_dir.parent)
    assert os.path.basename(svc._persistent_env_path()) == ".ai_env"


def test_new_ai_engine_service_uses_tmp_home(tmp_path):
    import api.services.ai_engine_config as aec
    svc = aec.AIEngineConfigService()
    assert _under(svc.config_path, tmp_path)
    assert _under(svc._persistent_env_path(), tmp_path)


def test_ai_engine_persistent_env_write_stays_in_tmp(isolate_provider_env, tmp_path):
    svc = isolate_provider_env
    os.environ["NVIDIA_API_KEY"] = "iso-test-value"
    try:
        svc._write_persistent_env()
    finally:
        os.environ.pop("NVIDIA_API_KEY", None)
    env_path = svc._persistent_env_path()
    assert os.path.isfile(env_path)
    assert _under(env_path, tmp_path)
