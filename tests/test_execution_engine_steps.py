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

    def execute_action(self, adapter, action, params):
        self.calls.append((adapter, action, params))
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
    def execute_action(self, adapter, action, params):
        self.calls.append((adapter, action, params))
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
            def execute_action(self, adapter, action, params):
                self.calls.append(adapter)
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


# ---------------------------------------------------------------------------
# SEC-12 (engine part): {{var}} substitution must not break out of JSON
# strings, and must keep value types.
# ---------------------------------------------------------------------------

def _resolve(sm, escalator, config, inputs=None, context=None):
    engine = ExecutionEngine(sm, FakeHub(), escalator)
    run = {"inputs": inputs or {}, "context": context or {}}
    return engine._resolve_context(config, run)


class TestResolveContext:
    def test_plain_string_substitution(self, sm, escalator):
        assert _resolve(sm, escalator, {"url": "https://{{host}}/x"}, {"host": "example.com"}) == \
            {"url": "https://example.com/x"}

    def test_context_takes_priority_over_inputs(self, sm, escalator):
        out = _resolve(sm, escalator, {"v": "{{name}}"},
                       inputs={"name": "from-input"}, context={"name": "from-context"})
        assert out == {"v": "from-context"}

    def test_input_used_when_no_context_value(self, sm, escalator):
        assert _resolve(sm, escalator, {"v": "{{name}}"}, inputs={"name": "x"}) == {"v": "x"}

    def test_double_quote_in_value_stays_a_string_value(self, sm, escalator):
        out = _resolve(sm, escalator, {"q": "say {{msg}} now"}, {"msg": 'he said "hi"'})
        assert out == {"q": 'say he said "hi" now'}

    def test_backslash_in_value_is_preserved(self, sm, escalator):
        out = _resolve(sm, escalator, {"p": "C:\\temp\\{{f}}"}, {"f": "a\\b"})
        assert out == {"p": "C:\\temp\\a\\b"}

    def test_injection_cannot_add_a_new_key(self, sm, escalator):
        payload = '", "admin": true, "x": "'
        out = _resolve(sm, escalator, {"name": "{{v}}"}, {"v": payload})
        assert out == {"name": payload}
        assert "admin" not in out

    def test_injection_with_closing_braces_stays_inside_value(self, sm, escalator):
        payload = '"}, "evil": {"a": "b'
        out = _resolve(sm, escalator, {"name": "{{v}}", "other": "ok"}, {"v": payload})
        assert set(out) == {"name", "other"}
        assert out["name"] == payload

    def test_whole_string_placeholder_keeps_int_type(self, sm, escalator):
        out = _resolve(sm, escalator, {"n": "{{count}}"}, {"count": 42})
        assert out == {"n": 42}
        assert isinstance(out["n"], int)

    def test_whole_string_placeholder_keeps_bool_and_none(self, sm, escalator):
        out = _resolve(sm, escalator, {"b": "{{flag}}", "z": "{{nothing}}"},
                       inputs={"flag": True, "nothing": None})
        assert out == {"b": True, "z": None}

    def test_whole_string_placeholder_keeps_list_and_dict(self, sm, escalator):
        out = _resolve(sm, escalator, {"items": "{{rows}}", "obj": "{{meta}}"},
                       inputs={"rows": [1, "two"], "meta": {"k": "v"}})
        assert out == {"items": [1, "two"], "obj": {"k": "v"}}

    def test_embedded_dict_value_is_json_text_not_python_repr(self, sm, escalator):
        out = _resolve(sm, escalator, {"msg": "data: {{meta}}"}, inputs={"meta": {"k": True}})
        assert out["msg"] == 'data: {"k": true}'
        assert "{'k'" not in out["msg"]

    def test_embedded_list_value_is_json_text(self, sm, escalator):
        out = _resolve(sm, escalator, {"msg": "ids={{ids}}"}, inputs={"ids": [1, 2]})
        assert out["msg"] == "ids=[1, 2]"

    def test_embedded_none_and_bool_are_json_text(self, sm, escalator):
        out = _resolve(sm, escalator, {"msg": "a={{a}} b={{b}}"}, inputs={"a": None, "b": False})
        assert out["msg"] == "a=null b=false"

    def test_nested_dict_and_list_are_walked(self, sm, escalator):
        config = {
            "outer": {"inner": ["{{x}}", {"deep": "v={{x}}"}]},
            "keep": 1,
        }
        out = _resolve(sm, escalator, config, {"x": "9"})
        assert out == {"outer": {"inner": ["9", {"deep": "v=9"}]}, "keep": 1}

    def test_nested_whole_placeholder_keeps_type(self, sm, escalator):
        out = _resolve(sm, escalator, {"a": {"b": ["{{n}}"]}}, {"n": 3})
        assert out == {"a": {"b": [3]}}

    def test_non_string_values_pass_through_unchanged(self, sm, escalator):
        config = {"i": 5, "f": 1.5, "b": False, "n": None, "l": [1, None]}
        assert _resolve(sm, escalator, config) == config

    def test_keys_are_not_substituted(self, sm, escalator):
        out = _resolve(sm, escalator, {"{{k}}": "v"}, {"k": "x"})
        assert out == {"{{k}}": "v"}

    def test_unknown_placeholder_is_left_unchanged(self, sm, escalator):
        assert _resolve(sm, escalator, {"v": "{{missing}}"}) == {"v": "{{missing}}"}
        assert _resolve(sm, escalator, {"v": "a {{missing}} b"}) == {"v": "a {{missing}} b"}

    def test_placeholder_with_spaces_is_matched_as_before(self, sm, escalator):
        assert _resolve(sm, escalator, {"v": "{{ name }}"}, {"name": "x"}) == {"v": "x"}

    def test_multiple_placeholders_in_one_string(self, sm, escalator):
        out = _resolve(sm, escalator, {"v": "{{a}}-{{b}}"}, {"a": 1, "b": "two"})
        assert out == {"v": "1-two"}

    def test_empty_config(self, sm, escalator):
        assert _resolve(sm, escalator, {}) == {}

    def test_input_config_is_not_mutated(self, sm, escalator):
        config = {"v": "{{x}}", "n": {"m": "{{x}}"}}
        snapshot = json.loads(json.dumps(config))
        _resolve(sm, escalator, config, {"x": 1})
        assert config == snapshot

    def test_resolved_value_reaches_the_hub(self, sm, escalator):
        hub = FakeHub()
        _template(sm, "sec12", [{"name": "Call", "type": "HTTP",
                                 "config": {"body": "{{payload}}", "q": "x \"{{payload}}\""}}])
        engine = ExecutionEngine(sm, hub, escalator)
        engine.start_run("sec12", {"payload": 'a"b\\c'})
        (adapter, action, params) = hub.calls[0]
        assert adapter == "HTTP"
        assert action == "fetch_resource"
        assert params == {"body": 'a"b\\c', "q": 'x "a"b\\c"'}


# ---------------------------------------------------------------------------
# W3 (P0-4): start_run must not return an id for a run that was not saved
# ---------------------------------------------------------------------------

class TestStartRunPersistence:
    def test_start_run_raises_when_run_cannot_be_saved(self, sm, escalator, monkeypatch):
        _template(sm, "p1", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        hub = FakeHub()
        engine = ExecutionEngine(sm, hub, escalator)
        monkeypatch.setattr(sm.runs, "create_run", lambda run_id, data: False)
        with pytest.raises(RuntimeError, match="could not be saved"):
            engine.start_run("p1", {})
        # Nothing ran and nothing was recorded.
        assert hub.calls == []
        assert sm.runs.get_all_runs() == {}

    def test_start_run_wraps_write_errors_in_runtime_error(self, sm, escalator, monkeypatch):
        _template(sm, "p2", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, FakeHub(), escalator)

        def boom(run_id, data):
            raise OSError("disk full")

        monkeypatch.setattr(sm.runs, "create_run", boom)
        with pytest.raises(RuntimeError, match="could not be saved") as info:
            engine.start_run("p2", {})
        assert isinstance(info.value.__cause__, OSError)

    def test_start_run_on_corrupt_runs_file_raises_runtime_error(self, sm, escalator, tmp_path):
        _template(sm, "p3", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        (tmp_path / "workflow_runs.json").write_text("{not json")
        with pytest.raises(RuntimeError):
            engine.start_run("p3", {})
        # The corrupt file is preserved, not overwritten.
        assert (tmp_path / "workflow_runs.json").read_text() == "{not json"

    def test_successful_start_run_returns_a_persisted_id(self, sm, escalator):
        _template(sm, "p4", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        run_id = ExecutionEngine(sm, FakeHub(), escalator).start_run("p4", {})
        assert sm.runs.get_run(run_id) is not None

    def test_unknown_template_still_raises_value_error(self, sm, escalator):
        with pytest.raises(ValueError):
            ExecutionEngine(sm, FakeHub(), escalator).start_run("nope", {})

    def test_engine_route_returns_500_when_run_cannot_be_saved(self, sm, escalator, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from api import engine_router

        _template(sm, "p5", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        monkeypatch.setattr(sm.runs, "create_run", lambda run_id, data: False)
        app = FastAPI()
        app.include_router(engine_router.router)
        app.state.engine = ExecutionEngine(sm, FakeHub(), escalator)
        r = TestClient(app).post("/api/engine/start", json={"template_id": "p5", "inputs": {}})
        assert r.status_code == 500
        assert "run_id" not in r.json()


# ---------------------------------------------------------------------------
# W3 (P0-3, R5): the timer thread must never die silently
# ---------------------------------------------------------------------------

class TestTimerGuard:
    def _failing_run(self, sm, escalator, timers, tid="g1"):
        _template(sm, tid, [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        run_id = engine.start_run(tid, {})
        (pending,) = _live(timers)
        return engine, run_id, pending

    def test_missing_template_at_fire_time_blocks_run_with_escalation(self, sm, escalator, timers):
        engine, run_id, pending = self._failing_run(sm, escalator, timers)
        assert sm.templates.delete_template("g1")
        pending.fire()  # must not raise
        assert _status(sm, run_id) == "BLOCKED"
        assert len(escalator.escalations) == 1
        assert "g1" in escalator.escalations[0]["error"]
        assert "not found" in escalator.escalations[0]["error"]
        types = [e["event_type"] for e in sm.runs.get_run_timeline(run_id)]
        assert "RUN_BLOCKED" in types
        assert _live(timers) == []

    def test_missing_template_does_not_raise_attribute_error(self, sm, escalator):
        _template(sm, "g2", [{"name": "A", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, FakeHub(), escalator)
        sm.runs.create_run("RUN-G2", {"template_id": "gone", "status": "RUNNING",
                                      "current_step_index": 0, "inputs": {}, "context": {}, "results": {}})
        engine.process_next_step("RUN-G2")  # used to raise AttributeError on None.get
        assert _status(sm, "RUN-G2") == "BLOCKED"
        assert len(escalator.escalations) == 1

    def test_corrupt_runs_file_at_fire_time_is_contained(self, sm, escalator, timers, tmp_path, caplog):
        engine, run_id, pending = self._failing_run(sm, escalator, timers, "g3")
        (tmp_path / "workflow_runs.json").write_text("{broken")
        with caplog.at_level("ERROR"):
            pending.fire()  # must not raise out of the timer thread
        assert any("Retry timer" in r.message for r in caplog.records)
        # The corrupt file is left alone; the escalation is still attempted.
        assert (tmp_path / "workflow_runs.json").read_text() == "{broken"
        assert len(escalator.escalations) == 1

    def test_claim_is_released_after_a_timer_crash(self, sm, escalator, timers):
        engine, run_id, pending = self._failing_run(sm, escalator, timers, "g4")
        sm.templates.delete_template("g4")
        pending.fire()
        claim = engine._claim_for(run_id)
        assert claim.acquire(blocking=False), "claim lock was left held"
        claim.release()

    def test_unexpected_error_in_advance_blocks_and_releases_claim(self, sm, escalator, timers, monkeypatch):
        engine, run_id, pending = self._failing_run(sm, escalator, timers, "g5")

        def explode(rid):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(engine, "_advance", explode)
        pending.fire()
        assert _status(sm, run_id) == "BLOCKED"
        assert "kaboom" in escalator.escalations[0]["error"]
        claim = engine._claim_for(run_id)
        assert claim.acquire(blocking=False)
        claim.release()

    def test_escalator_failure_inside_guard_is_swallowed(self, sm, timers):
        class BrokenEscalator:
            def escalate_to_orchestrator(self, **kw):
                raise RuntimeError("board down")

        _template(sm, "g6", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), BrokenEscalator(), RetryManager(sm))
        run_id = engine.start_run("g6", {})
        (pending,) = _live(timers)
        sm.templates.delete_template("g6")
        pending.fire()  # nothing escapes
        assert _status(sm, run_id) == "BLOCKED"
        types = [e["event_type"] for e in sm.runs.get_run_timeline(run_id)]
        assert "RUN_BLOCKED" in types

    def test_normal_retry_path_is_unchanged(self, sm, escalator, timers):
        _template(sm, "g7", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, FakeHub(fail_times=1), escalator, RetryManager(sm))
        run_id = engine.start_run("g7", {})
        (pending,) = _live(timers)
        pending.fire()
        assert _status(sm, run_id) == "COMPLETED"
        assert escalator.escalations == []


# ---------------------------------------------------------------------------
# W3 (R18): the retry budget is per step, not cumulative per run
# ---------------------------------------------------------------------------

class FlakyOnceHub:
    """Fails the first call of every distinct step name, then succeeds."""

    def __init__(self):
        self.seen = set()
        self.calls = []

    def execute_action(self, adapter, action, params):
        self.calls.append((adapter, action, params))
        key = params.get("key")
        if key not in self.seen:
            self.seen.add(key)
            raise RuntimeError("first attempt fails")
        return {"ok": True}


class TestRetryBudgetPerStep:
    def test_retry_count_resets_after_a_step_succeeds(self, sm, escalator, timers):
        _template(sm, "b1", [
            {"name": "One", "type": "HTTP", "config": {"key": "one"}},
            {"name": "Two", "type": "HTTP", "config": {"key": "two"}},
        ])
        engine = ExecutionEngine(sm, FlakyOnceHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("b1", {})
        assert sm.runs.get_run(run_id)["retry_count"] == 1
        (t1,) = _live(timers)
        t1.fire()  # step One succeeds, step Two fails once
        run = sm.runs.get_run(run_id)
        assert run["current_step_index"] == 1
        # Without the reset this would be 2: step One's failure would count against step Two.
        assert run["retry_count"] == 1
        assert [t.interval for t in timers.instances] == [300, 300]
        (t2,) = _live(timers)
        t2.fire()
        assert _status(sm, run_id) == "COMPLETED"
        assert sm.runs.get_run(run_id)["retry_count"] == 0

    def test_many_steps_each_failing_once_never_block(self, sm, escalator, timers):
        steps = [{"name": f"S{i}", "type": "HTTP", "config": {"key": f"k{i}"}} for i in range(5)]
        _template(sm, "b2", steps)
        engine = ExecutionEngine(sm, FlakyOnceHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("b2", {})
        for _ in range(5):
            live = _live(timers)
            if not live:
                break
            live[0].fire()
        assert _status(sm, run_id) == "COMPLETED"
        assert escalator.escalations == []

    def test_consecutive_failures_of_one_step_still_exhaust_the_budget(self, sm, escalator, timers):
        _template(sm, "b3", [{"name": "Fetch", "type": "HTTP", "config": {}}])
        engine = ExecutionEngine(sm, AlwaysFailHub(), escalator, RetryManager(sm))
        run_id = engine.start_run("b3", {})
        for _ in range(3):
            (pending,) = _live(timers)
            pending.fire()
        assert _status(sm, run_id) == "BLOCKED"
        assert sm.runs.get_run(run_id)["retry_count"] == 3
        assert len(escalator.escalations) == 1

    def test_success_without_retry_keeps_count_zero(self, sm, escalator):
        _template(sm, "b4", [{"name": "A", "type": "HTTP", "config": {}}])
        run_id = ExecutionEngine(sm, FakeHub(), escalator, RetryManager(sm)).start_run("b4", {})
        assert sm.runs.get_run(run_id).get("retry_count", 0) == 0
