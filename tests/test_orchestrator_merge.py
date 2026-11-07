"""
2.11 / T1 — run_pipeline must not clobber API edits made while a run is in
flight, and must not resurrect items deleted during the run.

Merge rule (decision D10, documented on ``Orchestrator.run_pipeline``): each
item is processed against a snapshot; the keys the handler changed are that
item's pipeline-owned changes; at commit time the latest state is re-read from
disk under the state lock and only those keys are written onto the fresh item.

These tests use the real pipeline-state.json (redirected to tmp_path by the
root conftest's ``isolate_data_dir`` fixture) and patch the LLM-backed agents.
"""
import json

import pytest
from unittest.mock import patch

from agents import orchestrator
from agents import state as state_module
from tests.test_helpers import make_item


def _seed(items):
    state_module.save_state({"last_heartbeat": None, "items": items})


def _load():
    return state_module.load_state()


def _api_edit(item_id, **fields):
    """Simulate the API (board_router) editing an item on disk mid-run."""
    st = state_module.load_state()
    st["items"][item_id].update(fields)
    state_module.save_state(st)


def _refined_item(**kw):
    item = make_item(stage="REFINEMENT", title="Original title", priority="low", **kw)
    item["complexity"] = "complex"  # skip the complexity estimate branch
    return item


class TestMergeDuringRun:
    def test_api_title_edit_during_refine_survives(self):
        """T1: an edit made while the refiner runs must not be overwritten."""
        _seed({"ID-001": _refined_item()})

        def refine_with_concurrent_edit(item_id, title):
            _api_edit("ID-001", title="Edited by API", priority="critical")
            return 85

        with patch("agents.orchestrator.refiner.refine_idea",
                   side_effect=refine_with_concurrent_edit):
            processed = orchestrator.run_pipeline()

        assert processed == 1
        final = _load()["items"]["ID-001"]
        # Pipeline-owned change applied:
        assert final["stage"] == "REVIEW_SPEC"
        assert final["confidence_score"] == 85
        # API-owned edits survive untouched:
        assert final["title"] == "Edited by API"
        assert final["priority"] == "critical"

    def test_edit_to_other_item_during_run_survives(self):
        _seed({
            "ID-001": _refined_item(),
            "ID-002": make_item(stage="INTAKE", title="Second"),
        })

        def refine_and_edit_other(item_id, title):
            _api_edit("ID-002", title="Renamed while running")
            return 80

        with patch("agents.orchestrator.refiner.refine_idea",
                   side_effect=refine_and_edit_other):
            orchestrator.run_pipeline()

        items = _load()["items"]
        assert items["ID-002"]["title"] == "Renamed while running"
        assert items["ID-002"]["stage"] == "REFINEMENT"  # INTAKE advanced by pipeline
        assert items["ID-001"]["stage"] == "REVIEW_SPEC"

    def test_handler_changes_are_applied_to_fresh_item(self):
        _seed({"ID-001": _refined_item()})
        with patch("agents.orchestrator.refiner.refine_idea", return_value=77):
            orchestrator.run_pipeline()
        final = _load()["items"]["ID-001"]
        assert final["stage"] == "REVIEW_SPEC"
        assert final["confidence_score"] == 77
        assert final["assigned_agent"] is None
        assert final["history"][-1]["stage"] == "REVIEW_SPEC"

    def test_item_deleted_during_run_is_not_resurrected(self):
        _seed({
            "ID-001": _refined_item(),
            "ID-002": make_item(stage="INTAKE", title="Survivor"),
        })

        def refine_then_delete_self(item_id, title):
            st = state_module.load_state()
            del st["items"]["ID-001"]
            state_module.save_state(st)
            return 90

        with patch("agents.orchestrator.refiner.refine_idea",
                   side_effect=refine_then_delete_self):
            processed = orchestrator.run_pipeline()

        items = _load()["items"]
        assert "ID-001" not in items
        assert items["ID-002"]["stage"] == "REFINEMENT"
        assert processed == 2  # both handlers completed; only the write for ID-001 is skipped

    def test_heartbeat_is_written(self):
        _seed({"ID-001": make_item(stage="DONE")})
        orchestrator.run_pipeline()
        assert _load()["last_heartbeat"] is not None

    def test_run_with_no_changes_still_saves_heartbeat(self):
        _seed({"ID-001": make_item(stage="REVIEW_SPEC", review_status="PENDING")})
        with patch.object(state_module, "save_state", wraps=state_module.save_state) as spy:
            orchestrator.run_pipeline()
        assert spy.call_count == 1
        assert _load()["last_heartbeat"] is not None

    def test_commit_saves_once_per_changed_item(self):
        _seed({
            "ID-001": make_item(stage="INTAKE"),
            "ID-002": make_item(stage="INTAKE"),
        })
        with patch.object(state_module, "save_state", wraps=state_module.save_state) as spy:
            orchestrator.run_pipeline()
        # one commit per changed item, plus one heartbeat commit
        assert spy.call_count == 3

    def test_handler_removed_key_is_removed_on_fresh_item(self):
        _seed({"ID-001": make_item(stage="INTAKE")})

        def drop_title(self_, item, state, item_id):
            item.pop("title", None)
            self_.transition_stage(item, "REFINEMENT", state, item_id)

        with patch("agents.orchestrator.Orchestrator.process_item", drop_title):
            orchestrator.run_pipeline()
        final = _load()["items"]["ID-001"]
        assert "title" not in final
        assert final["stage"] == "REFINEMENT"

    def test_fresh_state_read_happens_under_the_lock(self):
        """The commit re-reads and writes while the state lock is held."""
        _seed({"ID-001": make_item(stage="INTAKE")})
        seen = []
        real_load = state_module.load_state

        def spy_load():
            seen.append(state_module._lock.is_locked)
            return real_load()

        with patch("agents.orchestrator.state_module.load_state", side_effect=spy_load):
            orchestrator.run_pipeline()
        # First call is the initial snapshot; the commit re-read must be locked.
        assert seen[0] is False
        assert seen[-1] is True


class TestItemFailureIsolation:
    """2.12 — one failing item must not lose the batch."""

    def test_exception_in_one_item_leaves_it_on_disk_and_others_saved(self, caplog):
        _seed({
            "ID-001": make_item(stage="INTAKE", priority="high"),
            "ID-002": make_item(stage="INTAKE", priority="medium"),
            "ID-003": make_item(stage="INTAKE", priority="low"),
        })
        real_process = orchestrator.Orchestrator.process_item

        def flaky(self, item, state, item_id):
            if item_id == "ID-002":
                # Mutate the snapshot first to prove the partial change is discarded.
                item["stage"] = "BROKEN"
                raise RuntimeError("boom in handler")
            return real_process(self, item, state, item_id)

        with patch("agents.orchestrator.Orchestrator.process_item", flaky), \
             caplog.at_level("ERROR"):
            processed = orchestrator.run_pipeline()

        items = _load()["items"]
        assert items["ID-002"]["stage"] == "INTAKE"          # left as on disk
        assert items["ID-001"]["stage"] == "REFINEMENT"      # others committed
        assert items["ID-003"]["stage"] == "REFINEMENT"
        assert processed == 2
        assert any("ID-002" in r.getMessage() for r in caplog.records)

    def test_exception_is_logged_with_item_id_and_traceback(self, caplog):
        _seed({"ID-001": make_item(stage="INTAKE")})
        with patch("agents.orchestrator.Orchestrator.process_item",
                   side_effect=ValueError("kaput")), \
             caplog.at_level("ERROR"):
            orchestrator.run_pipeline()
        rec = [r for r in caplog.records if "ID-001" in r.getMessage()]
        assert rec, "failure must be logged with the item id"
        assert rec[0].exc_info is not None

    def test_commit_failure_for_one_item_does_not_stop_the_loop(self):
        _seed({
            "ID-001": make_item(stage="INTAKE", priority="high"),
            "ID-002": make_item(stage="INTAKE", priority="low"),
        })
        real_save = state_module.save_state
        calls = {"n": 0}

        def save_fail_first(st):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("disk full")
            return real_save(st)

        with patch("agents.orchestrator.state_module.save_state", side_effect=save_fail_first):
            processed = orchestrator.run_pipeline()

        items = _load()["items"]
        assert items["ID-001"]["stage"] == "INTAKE"
        assert items["ID-002"]["stage"] == "REFINEMENT"
        # processed counts items whose handler completed without error
        assert processed == 2
