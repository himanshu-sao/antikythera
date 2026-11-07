"""
Tests for Orchestrator actionable item selection and sorting.
"""
import pytest
from agents import orchestrator
from tests.test_helpers import make_items, make_item

class TestGetNextActionableItems:
    def test_returns_intake_items(self):
        """Items at INTAKE stage should be actionable."""
        state = make_items({"ID-001": make_item(stage="INTAKE")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1
        assert actionable[0][0] == "ID-001"

    def test_excludes_review_pending(self):
        """Items at REVIEW_SPEC with PENDING status should NOT be actionable."""
        state = make_items({
            "ID-001": make_item(stage="REVIEW_SPEC", review_status="PENDING"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 0

    def test_includes_review_approved(self):
        """Items at REVIEW_SPEC with APPROVED status should be actionable."""
        state = make_items({
            "ID-001": make_item(stage="REVIEW_SPEC", review_status="APPROVED"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1

    def test_includes_review_needs_revision(self):
        """2.14: NEEDS_REVISION must be actionable so the handler can send the item back."""
        state = make_items({
            "ID-001": make_item(stage="REVIEW_SPEC", review_status="NEEDS_REVISION"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1

    def test_sorts_by_priority(self):
        """Items should be sorted High first, then Medium, then Low."""
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority="Medium"),
            "ID-002": make_item(stage="INTAKE", priority="High"),
            "ID-003": make_item(stage="INTAKE", priority="Low"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert actionable[0][0] == "ID-002"  # High
        assert actionable[1][0] == "ID-001"  # Medium
        assert actionable[2][0] == "ID-003"  # Low

    def test_returns_refinement_items(self):
        """Items at REFINEMENT stage should be actionable."""
        state = make_items({"ID-001": make_item(stage="REFINEMENT")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1

    def test_returns_done_items_not_actionable(self):
        """Items at DONE stage should not be actionable."""
        state = make_items({"ID-001": make_item(stage="DONE")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1


class TestPriorityOrdering:
    """2.4 / T18 — the API stores lowercase priorities incl. 'critical'."""

    @staticmethod
    def _order(priorities):
        items = {
            f"ID-{i:03d}": make_item(stage="INTAKE", priority=p)
            for i, p in enumerate(priorities, start=1)
        }
        actionable = orchestrator.get_next_actionable_items(make_items(items))
        return [item["priority"] for _, item in actionable]

    def test_lowercase_priorities_sort(self):
        assert self._order(["low", "medium", "high"]) == ["high", "medium", "low"]

    def test_critical_sorts_first(self):
        assert self._order(["low", "high", "critical", "medium"]) == [
            "critical", "high", "medium", "low",
        ]

    def test_mixed_case_sorts_case_insensitively(self):
        assert self._order(["Low", "CRITICAL", "high", "Medium"]) == [
            "CRITICAL", "high", "Medium", "Low",
        ]

    def test_unknown_and_missing_priority_sort_last_or_as_medium(self):
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority="weird"),
            "ID-002": make_item(stage="INTAKE", priority="low"),
            "ID-003": make_item(stage="INTAKE", priority="high"),
        })
        ids = [i for i, _ in orchestrator.get_next_actionable_items(state)]
        assert ids == ["ID-003", "ID-002", "ID-001"]

    def test_missing_priority_treated_as_medium(self):
        a = make_item(stage="INTAKE")
        a.pop("priority", None)
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority="low"),
            "ID-002": a,
            "ID-003": make_item(stage="INTAKE", priority="high"),
        })
        ids = [i for i, _ in orchestrator.get_next_actionable_items(state)]
        assert ids == ["ID-003", "ID-002", "ID-001"]

    def test_non_string_priority_does_not_crash(self):
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority=None),
            "ID-002": make_item(stage="INTAKE", priority="high"),
        })
        ids = [i for i, _ in orchestrator.get_next_actionable_items(state)]
        assert ids[0] == "ID-002"


class TestReviewGateActionable:
    """2.14 — NEEDS_REVISION must reach the handler; APPROVED must not leak forward."""

    def test_needs_revision_at_review_stage_is_actionable(self):
        for stage in ("REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST"):
            state = make_items({
                "ID-001": make_item(stage=stage, review_status="NEEDS_REVISION"),
            })
            assert len(orchestrator.get_next_actionable_items(state)) == 1, stage

    def test_pending_review_still_not_actionable(self):
        for stage in ("REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST"):
            state = make_items({"ID-001": make_item(stage=stage, review_status="PENDING")})
            assert len(orchestrator.get_next_actionable_items(state)) == 0, stage

    def test_missing_review_status_still_not_actionable(self):
        item = make_item(stage="REVIEW_SPEC")
        item.pop("review_status")
        state = make_items({"ID-001": item})
        assert orchestrator.get_next_actionable_items(state) == []
