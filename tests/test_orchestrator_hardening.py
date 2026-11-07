"""P0-2 (corrupt state in the loop), P0-7 (run lock), P2-12 (poison item)."""
import json
import os
import threading
from unittest.mock import patch

import pytest
from filelock import FileLock

from agents import orchestrator
from agents import state as state_module
from tests.test_helpers import make_item


def _seed(items):
    state_module.save_state({"last_heartbeat": None, "items": items})


def _load():
    return state_module.load_state()


def _pipeline_lock_path():
    return state_module.STATE_FILE + ".pipeline.lock"


# --- P0-2 -----------------------------------------------------------------

class TestCorruptStateInLoop:
    def test_corrupt_state_returns_zero_and_logs_backup(self, caplog):
        with open(state_module.STATE_FILE, "w") as f:
            f.write("{not json")
        with caplog.at_level("ERROR"):
            assert orchestrator.run_pipeline() == 0
        errors = [r for r in caplog.records if r.levelname == "ERROR"]
        assert len(errors) == 1
        assert ".corrupt-" in errors[0].getMessage()
        # original untouched, one backup
        assert open(state_module.STATE_FILE).read() == "{not json"
        d = os.path.dirname(state_module.STATE_FILE)
        assert len([n for n in os.listdir(d) if ".corrupt-" in n]) == 1

    def test_repeated_cycles_keep_one_backup_and_retry_next_cycle(self):
        with open(state_module.STATE_FILE, "w") as f:
            f.write("[]")
        for _ in range(3):
            assert orchestrator.run_pipeline() == 0
        d = os.path.dirname(state_module.STATE_FILE)
        assert len([n for n in os.listdir(d) if ".corrupt-" in n]) == 1
        # operator repairs the file; next cycle works
        _seed({"ID-001": make_item(stage="INTAKE")})
        assert orchestrator.run_pipeline() == 1

    def test_corrupt_state_does_not_write_heartbeat_or_raise(self):
        with open(state_module.STATE_FILE, "w") as f:
            f.write("garbage")
        orchestrator.run_pipeline()
        assert open(state_module.STATE_FILE).read() == "garbage"

    def test_non_corrupt_load_error_also_returns_zero(self, caplog):
        with patch("agents.orchestrator.state_module.load_state", side_effect=OSError("denied")), \
             caplog.at_level("ERROR"):
            assert orchestrator.run_pipeline() == 0
        assert any("could not be loaded" in r.getMessage() for r in caplog.records)

    def test_lock_released_after_corrupt_cycle(self):
        with open(state_module.STATE_FILE, "w") as f:
            f.write("x")
        orchestrator.run_pipeline()
        probe = FileLock(_pipeline_lock_path())
        probe.acquire(timeout=0)
        probe.release()


# --- P0-7 -----------------------------------------------------------------

class TestRunLock:
    def test_second_call_while_held_returns_zero_without_processing(self, caplog):
        _seed({"ID-001": make_item(stage="INTAKE")})
        held = FileLock(_pipeline_lock_path())
        held.acquire()
        try:
            with patch("agents.orchestrator.Orchestrator.process_item") as proc, \
                 caplog.at_level("INFO"):
                assert orchestrator.run_pipeline() == 0
            proc.assert_not_called()
            assert any("pipeline already running" in r.getMessage() for r in caplog.records)
        finally:
            held.release()
        assert _load()["items"]["ID-001"]["stage"] == "INTAKE"
        assert _load()["last_heartbeat"] is None

    def test_overlapping_run_inside_handler_is_rejected(self):
        """A run started while another is mid-flight (same process, other lock object)."""
        _seed({"ID-001": make_item(stage="INTAKE")})
        inner = {}
        real = orchestrator.Orchestrator.process_item

        def reentrant(self, item, state, item_id):
            inner["n"] = orchestrator.Orchestrator().run_pipeline()
            return real(self, item, state, item_id)

        with patch("agents.orchestrator.Orchestrator.process_item", reentrant):
            assert orchestrator.run_pipeline() == 1
        assert inner["n"] == 0

    def test_concurrent_threads_only_one_processes(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        started, release = threading.Event(), threading.Event()
        real = orchestrator.Orchestrator.process_item
        results = []

        def slow(self, item, state, item_id):
            started.set()
            release.wait(5)
            return real(self, item, state, item_id)

        def worker():
            results.append(orchestrator.Orchestrator().run_pipeline())

        with patch("agents.orchestrator.Orchestrator.process_item", slow):
            t = threading.Thread(target=worker)
            t.start()
            assert started.wait(5)
            second = orchestrator.Orchestrator().run_pipeline()
            release.set()
            t.join(5)
        assert second == 0
        assert results == [1]

    def test_lock_released_after_handler_exception(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        with patch("agents.orchestrator.Orchestrator.process_item", side_effect=RuntimeError("x")):
            orchestrator.run_pipeline()
        probe = FileLock(_pipeline_lock_path())
        probe.acquire(timeout=0)
        probe.release()

    def test_lock_released_after_unexpected_exception(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        with patch("agents.orchestrator.Orchestrator.get_next_actionable_items",
                   side_effect=RuntimeError("bad")):
            with pytest.raises(RuntimeError):
                orchestrator.run_pipeline()
        probe = FileLock(_pipeline_lock_path())
        probe.acquire(timeout=0)
        probe.release()

    def test_run_lock_is_not_the_state_lock(self):
        assert _pipeline_lock_path() != state_module.LOCK_FILE
        _seed({"ID-001": make_item(stage="INTAKE")})
        # state_lock held by the commit path must work while the run lock is held
        assert orchestrator.run_pipeline() == 1
        assert _load()["items"]["ID-001"]["stage"] == "REFINEMENT"


# --- P2-12 ----------------------------------------------------------------

class TestPoisonItem:
    def _run_with_failing(self, n=1, ids=("ID-001",)):
        calls = []
        real = orchestrator.Orchestrator.process_item

        def flaky(self, item, state, item_id):
            calls.append(item_id)
            if item_id in ids:
                raise RuntimeError("poison")
            return real(self, item, state, item_id)

        with patch("agents.orchestrator.Orchestrator.process_item", flaky):
            for _ in range(n):
                orchestrator.run_pipeline()
        return calls

    def test_below_threshold_not_blocked(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        calls = self._run_with_failing(2)
        assert calls == ["ID-001"] * 2
        assert _load()["items"]["ID-001"]["blocked_reason"] is None

    def test_third_consecutive_failure_blocks_and_skips(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        calls = self._run_with_failing(6)
        assert calls == ["ID-001"] * 3  # skipped afterwards
        item = _load()["items"]["ID-001"]
        assert "3 consecutive failures" in item["blocked_reason"]
        assert "poison" in item["blocked_reason"]
        assert item["stage"] == "INTAKE"

    def test_blocking_only_merges_blocked_reason(self):
        _seed({"ID-001": make_item(stage="INTAKE", title="Keep")})
        before = _load()["items"]["ID-001"]
        self._run_with_failing(3)
        after = _load()["items"]["ID-001"]
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        assert changed == {"blocked_reason"}

    def test_success_resets_counter(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        real = orchestrator.Orchestrator.process_item
        outcomes = iter(["fail", "fail", "ok", "fail", "fail"])

        def scripted(self, item, state, item_id):
            if next(outcomes) == "fail":
                raise RuntimeError("poison")
            # success without moving the item
            return None

        with patch("agents.orchestrator.Orchestrator.process_item", scripted):
            for _ in range(5):
                orchestrator.run_pipeline()
        assert _load()["items"]["ID-001"]["blocked_reason"] is None

    def test_stage_change_unblocks(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        self._run_with_failing(3)
        # Someone moves the item (e.g. via the board) to another stage.
        st = _load()
        st["items"]["ID-001"]["stage"] = "REFINEMENT"
        state_module.save_state(st)
        calls = self._run_with_failing(1)
        assert calls == ["ID-001"]

    def test_other_items_keep_processing(self):
        _seed({
            "ID-001": make_item(stage="INTAKE", priority="high"),
            "ID-002": make_item(stage="INTAKE", priority="low"),
        })
        done = []

        def fake(self, item, state, item_id):
            if item_id == "ID-001":
                raise RuntimeError("poison")
            done.append(item_id)

        with patch("agents.orchestrator.Orchestrator.process_item", fake):
            for _ in range(4):
                orchestrator.run_pipeline()
        assert done == ["ID-002"] * 4
        assert _load()["items"]["ID-001"]["blocked_reason"]

    def test_counters_are_not_persisted(self):
        _seed({"ID-001": make_item(stage="INTAKE")})
        self._run_with_failing(2)
        raw = json.dumps(_load())
        assert "failure" not in raw

    def test_failure_does_not_commit_partial_handler_changes(self):
        _seed({"ID-001": make_item(stage="INTAKE")})

        def bad(self, item, state, item_id):
            item["stage"] = "BROKEN"
            raise RuntimeError("poison")

        with patch("agents.orchestrator.Orchestrator.process_item", bad):
            for _ in range(3):
                orchestrator.run_pipeline()
        item = _load()["items"]["ID-001"]
        assert item["stage"] == "INTAKE"
        assert item["blocked_reason"]
