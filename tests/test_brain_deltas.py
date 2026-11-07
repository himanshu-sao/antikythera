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


# ---------------------------------------------------------------------------
# 2.17: rule-4 ARTIFACT_COMMENT must not create empty REVISE deltas, and
# commit_delta must never truncate an artifact with empty content.
# ---------------------------------------------------------------------------

def _write_delta(deltas_dir, **fields):
    data = {
        "target_artifact": "memory.md",
        "change_type": "REVISE",
        "proposed_content": "",
        "reason": "r",
        "status": "PENDING",
        "confidence_score": 50,
    }
    data.update(fields)
    delta = CognitiveDelta(**data)
    path = os.path.join(deltas_dir, f"{delta.delta_id}.json")
    with open(path, "w") as f:
        f.write(delta.model_dump_json())
    return delta.delta_id


class TestArtifactCommentRule:
    def test_artifact_comment_creates_no_empty_revise_delta(self, brain, deltas_dir, knowledge_dir):
        observer = ObserverManager(brain, FakeRunManager())
        event = ObserverEvent(
            event_type="ARTIFACT_COMMENT",
            event_data={"target_artifact": "memory.md", "comment": "Please tighten this."},
        )
        deltas = observer.process_event(event)
        assert deltas == []
        assert os.listdir(deltas_dir) == []

    def test_artifact_comment_without_comment_creates_nothing(self, brain, deltas_dir):
        observer = ObserverManager(brain, FakeRunManager())
        event = ObserverEvent(event_type="ARTIFACT_COMMENT", event_data={"target_artifact": "memory.md"})
        assert observer.process_event(event) == []
        assert os.listdir(deltas_dir) == []


class TestCommitDeltaRefusesEmptyContent:
    def test_revise_with_empty_content_is_refused_and_artifact_untouched(self, brain, deltas_dir, knowledge_dir):
        artifact = os.path.join(knowledge_dir, "memory.md")
        with open(artifact, "w") as f:
            f.write("precious existing notes")
        delta_id = _write_delta(deltas_dir, change_type="REVISE", proposed_content="")
        assert brain.commit_delta(delta_id) is False
        assert open(artifact).read() == "precious existing notes"
        # Delta stays PENDING so a human can refine or reject it.
        assert brain.get_pending_deltas()[0].status == "PENDING"

    def test_replace_with_empty_content_is_refused(self, brain, deltas_dir, knowledge_dir):
        artifact = os.path.join(knowledge_dir, "user.md")
        with open(artifact, "w") as f:
            f.write("keep me")
        delta_id = _write_delta(deltas_dir, target_artifact="user.md", change_type="REPLACE", proposed_content="")
        assert brain.commit_delta(delta_id) is False
        assert open(artifact).read() == "keep me"

    def test_whitespace_only_revise_is_refused(self, brain, deltas_dir, knowledge_dir):
        artifact = os.path.join(knowledge_dir, "memory.md")
        with open(artifact, "w") as f:
            f.write("keep me")
        delta_id = _write_delta(deltas_dir, change_type="REVISE", proposed_content="  \n\t ")
        assert brain.commit_delta(delta_id) is False
        assert open(artifact).read() == "keep me"

    def test_revise_with_real_content_still_applies(self, brain, deltas_dir, knowledge_dir):
        artifact = os.path.join(knowledge_dir, "memory.md")
        with open(artifact, "w") as f:
            f.write("old")
        delta_id = _write_delta(deltas_dir, change_type="REVISE", proposed_content="new notes")
        assert brain.commit_delta(delta_id) is True
        assert open(artifact).read() == "new notes"
        assert json.load(open(os.path.join(deltas_dir, f"{delta_id}.json")))["status"] == "APPROVED"

    def test_replace_with_real_content_still_applies(self, brain, deltas_dir, knowledge_dir):
        artifact = os.path.join(knowledge_dir, "user.md")
        with open(artifact, "w") as f:
            f.write("old")
        delta_id = _write_delta(deltas_dir, target_artifact="user.md", change_type="REPLACE", proposed_content="fresh")
        assert brain.commit_delta(delta_id) is True
        assert open(artifact).read() == "fresh"

    def test_add_with_empty_content_is_unchanged_behaviour(self, brain, deltas_dir, knowledge_dir):
        # ADD appends; an empty append does not truncate, so it stays allowed.
        artifact = os.path.join(knowledge_dir, "memory.md")
        with open(artifact, "w") as f:
            f.write("keep")
        delta_id = _write_delta(deltas_dir, change_type="ADD", proposed_content="")
        assert brain.commit_delta(delta_id) is True
        assert open(artifact).read() == "keep\n"

    def test_missing_delta_returns_false(self, brain):
        assert brain.commit_delta("does-not-exist") is False
