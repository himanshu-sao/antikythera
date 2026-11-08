"""T8 (D2): steps dispatch on adapter + action through a real IntegrationHub.

Covers the engine call ``hub.execute_action(adapter, action, resolved_config)``,
the runtime migration of legacy ``type``-named steps, and a step with no action
failing cleanly through the retry path. A real IntegrationHub is used with a fake
native adapter module (installed in sys.modules for the test only). No network,
no LLM, no app singletons.
"""
import sys
import types

import pytest

from api.escalation_manager import EscalationManager
from api.execution_engine import ExecutionEngine
from api.integration_hub import IntegrationHub
from api.models.automation import HITL_STEP_TYPE, migrate_step
from api.retry_manager import RetryManager
from api.workflow_state_manager import WorkflowStateManager


FAKE_MODULE = "t8_fake_native_adapter"


class _FakeNativeAdapter:
    """Records every fetch call; the hub maps fetch_resource to fetch."""
    calls = []

    def __init__(self, vault=None):
        self.vault = vault

    async def fetch(self, resource_id, params=None):
        _FakeNativeAdapter.calls.append({"resource_id": resource_id, "arguments": params})
        return {"resource_id": resource_id, "arguments": params}


@pytest.fixture
def fake_adapter(monkeypatch):
    _FakeNativeAdapter.calls = []
    module = types.ModuleType(FAKE_MODULE)
    module.FakeNativeAdapter = _FakeNativeAdapter
    monkeypatch.setitem(sys.modules, FAKE_MODULE, module)
    return _FakeNativeAdapter


@pytest.fixture
def sm(tmp_path):
    return WorkflowStateManager(str(tmp_path))


@pytest.fixture
def hub(tmp_path, fake_adapter):
    h = IntegrationHub(str(tmp_path))
    # allow_any_module: this suite dispatches against a fake adapter module,
    # not a canonical api.adapters.* one (P1-3 test escape).
    assert h.add_integration("fake", "native", {"adapter_module": FAKE_MODULE},
                             allow_any_module=True)
    return h


class _Escalator:
    def __init__(self):
        self.escalations = []

    def escalate_to_orchestrator(self, run_id, step_name, error_message):
        self.escalations.append({"run_id": run_id, "step_name": step_name, "error": error_message})
        return "REC-T8"


def _save(sm, tid, steps):
    assert sm.templates.save_template(tid, {"name": tid, "steps": steps})


def _run(sm, run_id):
    return sm.runs.get_run(run_id)


def _events(sm, run_id):
    return [e["event_type"] for e in sm.runs.get_run_timeline(run_id)]


# ---------------------------------------------------------------------------
# New-shape dispatch
# ---------------------------------------------------------------------------

class TestNewShapeDispatch:
    def test_two_step_template_runs_to_completed_and_index_advances(self, sm, hub, fake_adapter):
        _save(sm, "t8-two", [
            {"name": "Fetch A", "adapter": "fake", "action": "fetch_resource",
             "config": {"resource_id": "A1"}, "next_step": None},
            {"name": "Fetch B", "adapter": "fake", "action": "fetch_resource",
             "config": {"resource_id": "B2"}, "next_step": None},
        ])
        engine = ExecutionEngine(sm, hub, _Escalator())
        run_id = engine.start_run("t8-two", {})

        run = _run(sm, run_id)
        assert run["status"] == "COMPLETED"
        assert run["current_step_index"] == 2
        assert [c["resource_id"] for c in fake_adapter.calls] == ["A1", "B2"]
        assert set(run["context"]) == {"Fetch A", "Fetch B"}
        assert run["context"]["Fetch A"]["status"] == "success"
        assert "RUN_COMPLETED" in _events(sm, run_id)

    def test_resolved_placeholders_reach_the_adapter(self, sm, hub, fake_adapter):
        _save(sm, "t8-vars", [
            {"name": "Fetch", "adapter": "fake", "action": "fetch_resource",
             "config": {"resource_id": "{{ticket}}", "arguments": {"note": "x {{ticket}}"}}},
        ])
        engine = ExecutionEngine(sm, hub, _Escalator())
        run_id = engine.start_run("t8-vars", {"ticket": "T-9"})
        assert _run(sm, run_id)["status"] == "COMPLETED"
        assert fake_adapter.calls == [{"resource_id": "T-9", "arguments": {"note": "x T-9"}}]

    def test_engine_passes_three_arguments_to_the_hub(self, sm, escalator_free=None):
        class RecordingHub:
            def __init__(self):
                self.calls = []

            def execute_action(self, adapter, action, params):
                self.calls.append((adapter, action, params))
                return {"status": "success", "result": {}}

        hub = RecordingHub()
        _save(sm, "t8-args", [{"name": "One", "adapter": "github", "action": "list_repos",
                               "config": {"org": "acme"}}])
        engine = ExecutionEngine(sm, hub, _Escalator())
        run_id = engine.start_run("t8-args", {})
        assert hub.calls == [("github", "list_repos", {"org": "acme"})]
        assert _run(sm, run_id)["status"] == "COMPLETED"

    def test_hitl_step_still_pauses_and_does_not_call_the_hub(self, sm, hub, fake_adapter):
        _save(sm, "t8-hitl", [
            {"name": "Gate", "type": HITL_STEP_TYPE, "target_phase": "REVIEW"},
            {"name": "Fetch", "adapter": "fake", "action": "fetch_resource",
             "config": {"resource_id": "R"}},
        ])
        escalator = _Escalator()
        engine = ExecutionEngine(sm, hub, escalator)
        run_id = engine.start_run("t8-hitl", {})
        assert _run(sm, run_id)["status"] == "WAITING_FOR_HUMAN"
        assert fake_adapter.calls == []
        assert escalator.escalations[0]["step_name"] == "Gate"


# ---------------------------------------------------------------------------
# Legacy shape runs through the in-code migration
# ---------------------------------------------------------------------------

class TestLegacyTemplateMigration:
    def test_legacy_type_named_step_runs_through_migration(self, sm, hub, fake_adapter):
        # The old engine read the integration name from ``type``; the stored template
        # keeps that shape and must still complete.
        _save(sm, "t8-legacy", [
            {"name": "Legacy", "type": "fake", "config": {"resource_id": "L1",
                                                          "arguments": {"k": "v"}}},
        ])
        engine = ExecutionEngine(sm, hub, _Escalator())
        run_id = engine.start_run("t8-legacy", {})
        assert _run(sm, run_id)["status"] == "COMPLETED"
        assert fake_adapter.calls == [{"resource_id": "L1", "arguments": {"k": "v"}}]

    def test_legacy_step_keeps_its_stored_template_unchanged(self, sm, hub):
        original = {"name": "Legacy", "type": "fake", "config": {"resource_id": "L2"}}
        _save(sm, "t8-keep", [dict(original)])
        ExecutionEngine(sm, hub, _Escalator()).start_run("t8-keep", {})
        stored = sm.templates.get_template("t8-keep")["steps"][0]
        assert stored == original

    def test_migrated_step_records_adapter_and_action_in_start_event(self, sm, hub):
        _save(sm, "t8-ev", [{"name": "Legacy", "type": "fake", "config": {"resource_id": "E"}}])
        run_id = ExecutionEngine(sm, hub, _Escalator()).start_run("t8-ev", {})
        starts = [e for e in sm.runs.get_run_timeline(run_id) if e["event_type"] == "STEP_START"]
        assert starts and starts[0]["payload"]["adapter"] == "fake"
        assert starts[0]["payload"]["action"] == "fetch_resource"


class TestMigrateStep:
    def test_type_naming_an_integration_becomes_adapter(self):
        out = migrate_step({"name": "S", "type": "github", "action": "list_repos", "config": {}})
        assert out == {"name": "S", "adapter": "github", "action": "list_repos", "config": {}}

    def test_missing_action_on_internal_takes_config_action(self):
        out = migrate_step({"type": "INTERNAL", "config": {"action": "add_comment", "body": "b"}})
        assert out["adapter"] == "INTERNAL"
        assert out["action"] == "add_comment"
        assert out["config"] == {"action": "add_comment", "body": "b"}

    def test_missing_action_elsewhere_defaults_to_fetch_resource(self):
        out = migrate_step({"type": "github", "config": {"action": "ignored_here"}})
        assert out["action"] == "fetch_resource"

    def test_blank_action_is_treated_as_missing(self):
        out = migrate_step({"type": "jira", "action": "  ", "config": {}})
        assert out["action"] == "fetch_resource"

    def test_own_action_wins_over_config_action(self):
        out = migrate_step({"type": "internal", "action": "list_items", "config": {"action": "move_item"}})
        assert out["action"] == "list_items"

    def test_hitl_step_is_returned_unchanged(self):
        step = {"name": "Gate", "type": HITL_STEP_TYPE, "target_phase": "X"}
        assert migrate_step(step) == step

    def test_step_with_an_adapter_is_not_migrated(self):
        step = {"type": "github", "adapter": "jira", "action": "list_tickets"}
        assert migrate_step(step) == step

    def test_explicit_null_adapter_is_left_for_the_validator(self):
        step = {"type": "github", "adapter": None}
        assert migrate_step(step) == step

    @pytest.mark.parametrize("bad_type", [None, "", "   ", 5, ["github"]])
    def test_unusable_type_is_left_unchanged(self, bad_type):
        step = {"type": bad_type, "config": {}}
        assert migrate_step(step) == step

    def test_input_is_not_mutated(self):
        step = {"type": "github", "config": {"org": "a"}}
        before = {"type": "github", "config": {"org": "a"}}
        migrate_step(step)
        assert step == before

    def test_non_dict_is_returned_as_is(self):
        assert migrate_step("github") == "github"
        assert migrate_step(None) is None


# ---------------------------------------------------------------------------
# A step with no adapter or no action fails cleanly through the retry path
# ---------------------------------------------------------------------------

class _NeverCalledHub:
    def __init__(self):
        self.calls = []

    def execute_action(self, adapter, action, params):
        self.calls.append((adapter, action, params))
        return {"status": "success", "result": {}}


class TestMissingActionFailsCleanly:
    def test_missing_action_goes_through_retry_path_not_a_crash(self, sm, tmp_path, monkeypatch):
        import threading

        scheduled = []

        class _Timer:
            def __init__(self, interval, fn):
                self.interval, self.fn = interval, fn
                self.daemon = False
                scheduled.append(self)

            def start(self):
                pass

            def cancel(self):
                pass

        monkeypatch.setattr(threading, "Timer", _Timer)
        hub = _NeverCalledHub()
        _save(sm, "t8-noact", [{"name": "NoAction", "adapter": "fake", "config": {"resource_id": "X"}}])
        engine = ExecutionEngine(sm, hub, _Escalator(), RetryManager(sm))
        run_id = engine.start_run("t8-noact", {})

        assert hub.calls == [], "a step with no action must never reach the hub"
        run = _run(sm, run_id)
        assert run["status"] == "RUNNING"  # retry scheduled, not BLOCKED yet
        assert run["retry_count"] == 1
        assert [t.interval for t in scheduled] == [300]
        assert "RUN_BLOCKED" not in _events(sm, run_id)

    def test_missing_action_reason_is_recorded_on_the_retry(self, sm, monkeypatch):
        import threading

        class _Timer:
            def __init__(self, interval, fn):
                self.interval, self.fn, self.daemon = interval, fn, False

            def start(self):
                pass

            def cancel(self):
                pass

        monkeypatch.setattr(threading, "Timer", _Timer)
        _save(sm, "t8-reason", [{"name": "NoAction", "adapter": "fake", "config": {}}])
        engine = ExecutionEngine(sm, _NeverCalledHub(), _Escalator(), RetryManager(sm))
        run_id = engine.start_run("t8-reason", {})
        failures = [e for e in sm.runs.get_run_timeline(run_id) if e["event_type"] == "FAILURE"]
        assert len(failures) == 1
        assert "NoAction" in failures[0]["payload"]["error"]
        assert "no action" in failures[0]["payload"]["error"]

    def test_missing_adapter_fails_cleanly_and_blocks_after_retries(self, sm, monkeypatch):
        import threading

        class _Timer:
            def __init__(self, interval, fn):
                self.interval, self.fn, self.daemon = interval, fn, False

            def start(self):
                pass

            def cancel(self):
                pass

        monkeypatch.setattr(threading, "Timer", _Timer)
        hub = _NeverCalledHub()
        _save(sm, "t8-noadapter", [{"name": "NoAdapter", "action": "fetch_resource", "config": {}}])
        escalator = _Escalator()
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("t8-noadapter", {})
        for _ in range(3):
            engine.process_next_step(run_id)  # each manual trigger is one more attempt
        assert hub.calls == []
        assert _run(sm, run_id)["status"] == "BLOCKED"
        assert escalator.escalations and escalator.escalations[-1]["step_name"] == "NoAdapter"


# ---------------------------------------------------------------------------
# Validator: one clear violation per bad step (regression)
# ---------------------------------------------------------------------------

class TestValidatorReportsOneViolationPerBadStep:
    def _violations(self, steps):
        import api.main  # noqa: F401  (import order: workflow_router imports api.main)
        from api.workflow_router import _validate_step_shape, _validate_template_adapters
        return _validate_template_adapters({"steps": steps}), _validate_step_shape({"steps": steps})

    def test_ui_action_type_reports_only_the_type_violation(self):
        adapter_v, shape_v = self._violations(
            [{"id": 1, "type": "action", "action": "list_items", "config": {"action": "list_items"}}])
        assert adapter_v == []  # no misleading "adapter 'action' not in allowlist"
        assert len(shape_v) == 1 and "type 'action'" in shape_v[0]

    def test_legacy_integration_type_is_not_a_violation_in_the_allowlist(self):
        adapter_v, _ = self._violations([{"id": 2, "type": "github", "config": {}}])
        assert adapter_v == []

    def test_execution_capable_type_is_still_blocked_by_sec13(self):
        adapter_v, _ = self._violations(
            [{"id": 3, "type": "bob_shell", "action": "run", "config": {}}])
        assert adapter_v and "bob_shell" in adapter_v[0]

    def test_hitl_step_has_no_shape_violation(self):
        adapter_v, shape_v = self._violations(
            [{"id": 4, "type": HITL_STEP_TYPE, "target_phase": "X"}])
        assert shape_v == [] and adapter_v == []


class TestMigrateStoredTemplateShapes:
    """The stored workflow_templates.json shapes (no top-level type or adapter)."""

    def test_config_adapter_is_promoted(self):
        step = {
            "step_id": "S1", "name": "Fetch merged PR", "category": "FETCH",
            "config": {"adapter": "github", "action": "fetch_resource",
                       "description": "d", "resource_id": "{{number}}"},
            "next_step": "S2",
        }
        m = migrate_step(step)
        assert m["adapter"] == "github"
        assert m["action"] == "fetch_resource"
        assert "type" not in m
        assert m["config"]["adapter"] == "github"  # config untouched
        assert step.get("adapter") is None  # input not mutated

    def test_config_adapter_is_lowercased(self):
        step = {"step_id": "S1", "config": {"adapter": "BOB_SHELL", "prompt": "p"}}
        m = migrate_step(step)
        assert m["adapter"] == "bob_shell"
        # bob_shell only implements execute (config prompt/args); its fetch
        # raises NotImplementedError, so the legacy default action is remapped.
        assert m["action"] == "execute"

    def test_internal_default_without_config_adapter(self):
        # AUTO-MOVE-TEST shape: config.action but no config.adapter.
        step = {
            "step_id": "S1", "name": "Move to Refinement", "category": "ACTION",
            "config": {"action": "move_item", "new_stage": "REFINEMENT",
                       "item_id": "RUN-TEST-ITEM"},
            "next_step": "S2",
        }
        m = migrate_step(step)
        assert m["adapter"] == "internal"
        assert m["action"] == "move_item"

    def test_no_adapter_anywhere_is_unchanged(self):
        step = {"step_id": "S1", "config": {"description": "nothing usable"}}
        assert migrate_step(step) == step

    def test_explicit_null_adapter_still_unchanged(self):
        step = {"step_id": "S1", "adapter": None, "config": {"adapter": "github"}}
        assert migrate_step(step) == step


class TestBobShellActionMigration:
    """The stored AI_INTEGRATION_BOB shape: config.adapter BOB_SHELL, no
    action, config prompt/args. BobShellAdapter only implements execute, so
    a migrated bob_shell step whose action resolves to fetch_resource (whose
    fetch raises NotImplementedError) runs execute instead. Every other
    migration rule is unchanged."""

    def test_stored_bob_shell_shape_migrates_to_execute(self):
        # The exact stored AI_INTEGRATION_BOB step shape.
        step = {
            "step_id": "S1", "name": "Run Bob Shell Analysis", "category": "ACTION",
            "config": {"adapter": "BOB_SHELL", "prompt": "Analyze recent changes",
                       "args": ["--yolo"], "api_key_env": "IBM_BOB_SHELL_DEFAULT_KEY"},
            "next_step": None,
        }
        m = migrate_step(step)
        assert m["adapter"] == "bob_shell"
        assert m["action"] == "execute"
        assert m["config"]["prompt"] == "Analyze recent changes"

    def test_legacy_type_named_bob_shell_step_migrates_to_execute(self):
        m = migrate_step({"name": "S", "type": "BOB_SHELL", "config": {"prompt": "p"}})
        assert m["adapter"] == "BOB_SHELL"
        assert m["action"] == "execute"

    def test_bob_shell_explicit_fetch_resource_action_is_remapped(self):
        m = migrate_step({"step_id": "S1", "config": {"adapter": "bob_shell",
                                                      "action": "fetch_resource"}})
        assert m["adapter"] == "bob_shell"
        assert m["action"] == "execute"

    def test_bob_shell_own_non_default_action_is_kept(self):
        m = migrate_step({"name": "S", "type": "bob_shell", "action": "analyze",
                          "config": {}})
        assert m["action"] == "analyze"

    def test_other_adapters_still_default_to_fetch_resource(self):
        for adapter in ("github", "jira", "internal", "GITHUB"):
            m = migrate_step({"name": "S", "type": adapter, "config": {}})
            assert m["action"] == "fetch_resource", adapter
            m = migrate_step({"step_id": "S1", "config": {"adapter": adapter}})
            assert m["action"] == "fetch_resource", adapter

    def test_internal_default_branch_is_not_affected(self):
        # config.action with no config.adapter still resolves to internal.
        m = migrate_step({"step_id": "S1", "config": {"action": "move_item"}})
        assert m["adapter"] == "internal"
        assert m["action"] == "move_item"
