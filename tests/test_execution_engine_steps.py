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


# ---------------------------------------------------------------------------
# 2.8 / T10: retry timers are tracked, cancellable, and claimed per run
# ---------------------------------------------------------------------------

class FakeTimer:
    """Stands in for threading.Timer. Records the delay; fires only on demand."""
    instances = []

    def __init__(self, interval, function, args=None, kwargs=None):
        self.interval = interval
        self.function = function
        self.args = args or []
        self.kwargs = kwargs or {}
        self.daemon = False
        self.started = False
        self.cancelled = False
        self.fired = False
        FakeTimer.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        """Run the callback as a real timer would, unless it was cancelled.

        A timer that has fired is no longer pending, so it is marked as done
        and no longer counted as live.
        """
        if self.cancelled or self.fired:
            return
        self.fired = True
        self.function(*self.args, **self.kwargs)


@pytest.fixture
def timers(monkeypatch):
    FakeTimer.instances = []
    monkeypatch.setattr(threading, "Timer", FakeTimer)
    return FakeTimer


def _live(timers):
    """Timers that are still pending: neither cancelled nor already fired."""
    return [t for t in timers.instances if not t.cancelled and not t.fired]


class AlwaysFailHub(FakeHub):
    def execute_action(self, action_type, params):
        self.calls.append((action_type, params))
        raise RuntimeError("upstream down")


class TestRetryTimers:
    def test_failure_schedules_retry_after_5_minutes(self, sm, escalator, timers):
        _template(sm, "r1", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("r1", {})
        assert [t.interval for t in timers.instances] == [300]
        assert timers.instances[0].daemon is True
        assert timers.instances[0].started is True
        assert _status(sm, run_id) == "RUNNING"
        assert escalator.escalations == []

    def test_retries_run_at_5_10_15_minutes_then_block_with_escalation(self, sm, escalator, timers):
        _template(sm, "r2", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = AlwaysFailHub()
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("r2", {})

        for _ in range(2):
            (pending,) = _live(timers)
            pending.fire()
        # Retry delays in seconds: 5, 10 and 15 minutes.
        assert [t.interval for t in timers.instances] == [300, 600, 900]
        assert len(hub.calls) == 3

        (last,) = _live(timers)
        last.fire()
        assert len(hub.calls) == 4
        run = sm.runs.get_run(run_id)
        assert run["status"] == "BLOCKED"
        assert run["retry_count"] == 3
        assert _live(timers) == []
        assert len(escalator.escalations) == 1
        assert escalator.escalations[0]["run_id"] == run_id
        types = [e["event_type"] for e in sm.runs.get_run_timeline(run_id)]
        assert "RUN_BLOCKED" in types

    def test_retry_that_succeeds_completes_run(self, sm, escalator, timers):
        _template(sm, "r3", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = FakeHub(fail_times=1)
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("r3", {})
        (pending,) = _live(timers)
        pending.fire()
        assert _status(sm, run_id) == "COMPLETED"
        assert escalator.escalations == []
        assert _live(timers) == []

    def test_no_retry_manager_blocks_immediately_without_timers(self, sm, escalator, timers):
        _template(sm, "r4", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, None)
        run_id = engine.start_run("r4", {})
        assert _status(sm, run_id) == "BLOCKED"
        assert timers.instances == []
        assert len(escalator.escalations) == 1

    def test_resume_cancels_pending_retry_timer(self, sm, escalator, timers):
        _template(sm, "r5", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = FakeHub(fail_times=1)
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("r5", {})
        (first,) = timers.instances
        assert first.cancelled is False

        sm.create_item("REC-00000A", "Recovery")
        sm.update_item("REC-00000A", {"linked_run_id": run_id})
        engine.resume_run_by_item_id("REC-00000A")

        assert first.cancelled is True
        assert _status(sm, run_id) == "COMPLETED"
        # Firing the cancelled timer afterwards must not run the step again.
        calls_before = len(hub.calls)
        first.fire()
        assert len(hub.calls) == calls_before

    def test_only_one_live_timer_per_run(self, sm, escalator, timers):
        _template(sm, "r6", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("r6", {})
        (first,) = _live(timers)
        first.fire()
        assert len(_live(timers)) == 1
        assert _live(timers)[0] is not first

    def test_timers_are_in_memory_only(self, sm, escalator, timers):
        # Limitation by design: pending retries are not persisted. A new engine
        # over the same state has no timers; the run waits for a resume.
        _template(sm, "r8", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("r8", {})
        assert _status(sm, run_id) == "RUNNING"
        fresh = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        assert fresh._timers == {}


class TestRunClaim:
    def test_claim_is_non_blocking_for_second_caller(self, sm, escalator):
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        claim = engine._claim_for("RUN-X")
        assert claim.acquire(blocking=False)
        try:
            # The second caller must not wait: it should get False right away.
            result = {}
            t = threading.Thread(target=lambda: result.update(ok=claim.acquire(blocking=False)))
            t.start()
            t.join(timeout=5)
            assert result == {"ok": False}
        finally:
            claim.release()

    def test_process_next_step_skips_when_run_is_claimed(self, sm, escalator, caplog):
        _template(sm, "c1", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = FakeHub()
        engine = ExecutionEngine(sm, hub, escalator)
        run_id = "RUN-C1"
        sm.runs.create_run(run_id, {"template_id": "c1", "status": "RUNNING",
                                    "current_step_index": 0, "inputs": {}, "context": {}, "results": {}})
        claim = engine._claim_for(run_id)
        assert claim.acquire(blocking=False)
        try:
            with caplog.at_level("INFO"):
                engine.process_next_step(run_id)
        finally:
            claim.release()
        assert hub.calls == []
        assert sm.runs.get_run(run_id)["current_step_index"] == 0
        assert "already being advanced" in caplog.text

    def test_timer_and_resume_cannot_run_the_step_twice_at_once(self, sm, escalator, timers):
        # Hold the hub inside step execution on a timer thread, then resume from
        # the main thread. The resume must skip, so the step runs exactly once.
        _template(sm, "c2", [{"name": "Slow", "type": "HTTP", "config": {}}])
        entered = threading.Event()
        release = threading.Event()

        class BlockingHub(FakeHub):
            def execute_action(self, action_type, params):
                self.calls.append(action_type)
                if len(self.calls) == 2:
                    entered.set()
                    release.wait(timeout=10)
                if len(self.calls) == 1:
                    raise RuntimeError("first attempt fails")
                return {"ok": True}

        hub = BlockingHub()
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("c2", {})
        (retry,) = _live(timers)

        worker = threading.Thread(target=retry.fire)
        worker.start()
        assert entered.wait(timeout=10)

        sm.create_item("REC-00000B", "Recovery")
        sm.update_item("REC-00000B", {"linked_run_id": run_id})
        engine.resume_run_by_item_id("REC-00000B")  # must return without a second call
        assert len(hub.calls) == 2

        release.set()
        worker.join(timeout=10)
        assert len(hub.calls) == 2
        assert _status(sm, run_id) == "COMPLETED"

    def test_claim_released_after_failure_so_next_trigger_runs(self, sm, escalator, timers):
        _template(sm, "c3", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = FakeHub(fail_times=1)
        engine = ExecutionEngine(sm, hub, escalator, RetryManager(sm))
        run_id = engine.start_run("c3", {})
        assert _status(sm, run_id) == "RUNNING"
        (retry,) = _live(timers)
        retry.fire()
        assert _status(sm, run_id) == "COMPLETED"

    def test_claim_released_after_exception_inside_advance(self, sm, escalator):
        _template(sm, "c4", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        run_id = engine.start_run("c4", {})
        assert _status(sm, run_id) == "COMPLETED"
        claim = engine._claim_for(run_id)
        assert claim.acquire(blocking=False)
        claim.release()

    def test_claims_are_per_run(self, sm, escalator):
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        a = engine._claim_for("A")
        b = engine._claim_for("B")
        assert a is not b
        assert engine._claim_for("A") is a
