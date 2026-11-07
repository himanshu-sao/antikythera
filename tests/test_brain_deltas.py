"""Regression and behaviour tests for brain delta generation and commit.

All filesystem access is confined to pytest's ``tmp_path``. No LLMs, no network.
"""
import json
import os

import pytest

from api.brain_managers import BrainManager, ObserverManager
from api.brain_schemas import CognitiveDelta, ObserverEvent


class FakeRunManager:
    """Stands in for RunManager: serves a fixed timeline per run id."""

    def __init__(self, timelines=None):
        self.timelines = timelines or {}

    def get_run_timeline(self, run_id):
        return list(self.timelines.get(run_id, []))


@pytest.fixture
def knowledge_dir(tmp_path):
    d = tmp_path / "knowledge"
    d.mkdir()
    return str(d)


@pytest.fixture
def deltas_dir(tmp_path):
    d = tmp_path / "deltas"
    d.mkdir()
    return str(d)


@pytest.fixture
def brain(knowledge_dir, deltas_dir):
    return BrainManager(knowledge_dir, deltas_dir)


def _observer(brain, timeline):
    return ObserverManager(brain, FakeRunManager({"RUN-1": timeline}))


# ---------------------------------------------------------------------------
# 2.3 / T13: analyze_kanban_logs must not crash on non-TASK_COMPLETED events
# ---------------------------------------------------------------------------

class TestAnalyzeKanbanLogs:
    def test_run_started_then_task_completed_does_not_raise(self, brain):
        timeline = [
            {"event_type": "RUN_STARTED", "payload": {}},
            {"event_type": "TASK_COMPLETED", "payload": {"summary": "Built the parser. It handles CSV."}},
        ]
        deltas = _observer(brain, timeline).analyze_kanban_logs("RUN-1")
        assert len(deltas) == 1
        assert deltas[0].target_artifact == "skills.md"
        assert deltas[0].proposed_content == "## Built the parser\n- Built the parser. It handles CSV."

    def test_events_without_task_completed_return_no_deltas(self, brain):
        timeline = [
            {"event_type": "RUN_STARTED", "payload": {}},
            {"event_type": "STEP_START", "payload": {"step": 1}},
            {"event_type": "STEP_END", "payload": {}},
        ]
        assert _observer(brain, timeline).analyze_kanban_logs("RUN-1") == []

    def test_empty_timeline_returns_no_deltas(self, brain):
        assert _observer(brain, []).analyze_kanban_logs("RUN-1") == []

    def test_task_completed_without_summary_returns_no_deltas(self, brain):
        timeline = [{"event_type": "TASK_COMPLETED", "payload": {}}]
        assert _observer(brain, timeline).analyze_kanban_logs("RUN-1") == []

    def test_summary_from_earlier_event_is_not_reused(self, brain):
        # A TASK_COMPLETED with a summary followed by one without must yield
        # exactly one delta, not a second one reusing the earlier summary.
        timeline = [
            {"event_type": "TASK_COMPLETED", "payload": {"summary": "First task done."}},
            {"event_type": "RUN_STARTED", "payload": {}},
        ]
        deltas = _observer(brain, timeline).analyze_kanban_logs("RUN-1")
        assert [d.proposed_content for d in deltas] == ["## First task done\n- First task done."]

    def test_task_failure_still_produces_memory_delta(self, brain):
        timeline = [
            {"event_type": "TASK_FAILURE", "payload": {"task_name": "lint", "error": "boom"}},
            {"event_type": "TASK_COMPLETED", "payload": {"summary": "Ok."}},
        ]
        deltas = _observer(brain, timeline).analyze_kanban_logs("RUN-1")
        targets = [d.target_artifact for d in deltas]
        assert targets == ["memory.md", "skills.md"]
        assert "lint" in deltas[0].proposed_content and "boom" in deltas[0].proposed_content

    def test_unknown_run_returns_no_deltas(self, brain):
        assert _observer(brain, []).analyze_kanban_logs("MISSING") == []
