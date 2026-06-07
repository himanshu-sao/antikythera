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

    def test_excludes_review_needs_revision(self):
        """Items at REVIEW_SPEC with NEEDS_REVISION should NOT be actionable."""
        state = make_items({
            "ID-001": make_item(stage="REVIEW_SPEC", review_status="NEEDS_REVISION"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 0

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
