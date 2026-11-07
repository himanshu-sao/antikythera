"""ExecutionEngine step handling: HITL resume (2.7, T9), retry timers and
run claims (2.8, T10), and {{var}} context resolution (SEC-12 engine part).

Everything is built on a WorkflowStateManager rooted in tmp_path with fake
hub/escalator collaborators. No LLM, no network, no app singletons.
"""
import json
import threading

import pytest

from api.execution_engine import ExecutionEngine
from api.retry_manager import RetryManager
from api.workflow_state_manager import WorkflowStateManager


class FakeHub:
    """Records calls. Returns a canned result. Can be told to fail."""

    def __init__(self, fail_times=0):
        self.calls = []
        self.fail_times = fail_times

    def execute_action(self, action_type, params):
        self.calls.append((action_type, params))
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("upstream unavailable")
        return {"ok": True, "echo": params}


class FakeEscalator:
    def __init__(self):
        self.escalations = []

    def escalate_to_orchestrator(self, run_id, step_name, error_message):
        self.escalations.append({"run_id": run_id, "step_name": step_name, "error": error_message})
        return f"REC-{run_id[-6:]}"


@pytest.fixture
def sm(tmp_path):
    return WorkflowStateManager(str(tmp_path))


@pytest.fixture
def escalator():
    return FakeEscalator()


def _template(sm, tid, steps):
    assert sm.templates.save_template(tid, {"name": tid, "steps": steps})


def _hitl(name, phase="DISCOVERY"):
    return {"name": name, "type": "ORCHESTRATOR_TASK", "target_phase": phase}


def _status(sm, run_id):
    return sm.runs.get_run(run_id)["status"]


# ---------------------------------------------------------------------------
# 2.7 / T9: HITL steps must finish after resume
# ---------------------------------------------------------------------------

class TestHitlResume:
    def _link(self, sm, item_id, run_id):
        assert sm.create_item(item_id, "Recovery")
        sm.update_item(item_id, {"linked_run_id": run_id})

    def test_two_hitl_steps_pause_resume_pause_resume_completes(self, sm, escalator, tmp_path):
        _template(sm, "t2", [_hitl("Approve A"), _hitl("Approve B")])
        engine = ExecutionEngine(sm, FakeHub(), escalator)

        run_id = engine.start_run("t2", {})
        assert _status(sm, run_id) == "WAITING_FOR_HUMAN"
        assert len(escalator.escalations) == 1
        assert sm.runs.get_run(run_id)["current_step_index"] == 0

        self._link(sm, "REC-000001", run_id)
        engine.resume_run_by_item_id("REC-000001")

        # After the first resume the first HITL step is finished, so the run
        # pauses at the second HITL step, not at the first again.
        assert _status(sm, run_id) == "WAITING_FOR_HUMAN"
        assert sm.runs.get_run(run_id)["current_step_index"] == 1
        assert [e["step_name"] for e in escalator.escalations] == ["Approve A", "Approve B"]

        engine.resume_run_by_item_id("REC-000001")
        assert _status(sm, run_id) == "COMPLETED"
        assert sm.runs.get_run(run_id)["current_step_index"] == 2

    def test_resume_does_not_repeat_the_same_hitl_step(self, sm, escalator):
        _template(sm, "t-once", [_hitl("Only"), _hitl("Second")])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        run_id = engine.start_run("t-once", {})
        self._link(sm, "REC-000002", run_id)
        engine.resume_run_by_item_id("REC-000002")
        names = [e["step_name"] for e in escalator.escalations]
        assert names.count("Only") == 1

    def test_single_hitl_step_completes_on_resume(self, sm, escalator):
        _template(sm, "t1", [_hitl("Solo")])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        run_id = engine.start_run("t1", {})
        assert _status(sm, run_id) == "WAITING_FOR_HUMAN"
        self._link(sm, "REC-000003", run_id)
        engine.resume_run_by_item_id("REC-000003")
        assert _status(sm, run_id) == "COMPLETED"
        assert len(escalator.escalations) == 1

    def test_resume_records_run_events_for_each_step(self, sm, escalator):
        _template(sm, "t-ev", [_hitl("A"), _hitl("B")])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        run_id = engine.start_run("t-ev", {})
        self._link(sm, "REC-000004", run_id)
        engine.resume_run_by_item_id("REC-000004")
        engine.resume_run_by_item_id("REC-000004")
        timeline = sm.runs.get_run_timeline(run_id)
        types = [e["event_type"] for e in timeline]
        assert types.count("RUN_PAUSED") == 2
        assert types[-1] == "RUN_COMPLETED"

    def test_hitl_step_does_not_call_the_hub(self, sm, escalator):
        hub = FakeHub()
        _template(sm, "t-hub", [_hitl("A")])
        engine = ExecutionEngine(sm, hub, escalator)
        engine.start_run("t-hub", {})
        assert hub.calls == []

    def test_resuming_a_blocked_run_at_a_hitl_step_does_not_skip_it(self, sm, escalator):
        # Only a run that was WAITING_FOR_HUMAN has had its HITL step answered.
        # A BLOCKED run being retried must re-attempt the step, not skip it.
        _template(sm, "t-blocked", [_hitl("Gate"), _hitl("After")])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        run_id = engine.start_run("t-blocked", {})
        sm.runs.update_run(run_id, {"status": "BLOCKED"})
        self._link(sm, "REC-000006", run_id)
        engine.resume_run_by_item_id("REC-000006")
        assert sm.runs.get_run(run_id)["current_step_index"] == 0
        assert _status(sm, run_id) == "WAITING_FOR_HUMAN"
        assert [e["step_name"] for e in escalator.escalations] == ["Gate", "Gate"]

    def test_resume_unknown_item_raises(self, sm, escalator):
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        with pytest.raises(ValueError):
            engine.resume_run_by_item_id("REC-NOPE")

    def test_resume_item_without_linked_run_raises(self, sm, escalator):
        sm.create_item("REC-000007", "Recovery")
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        with pytest.raises(ValueError):
            engine.resume_run_by_item_id("REC-000007")
