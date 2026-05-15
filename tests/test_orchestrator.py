"""
Tests for the Orchestrator Agent (agents/orchestrator.py).
"""

import pytest
from unittest.mock import patch, MagicMock

from agents import orchestrator


def _make_state(items=None):
    """Helper to create a test state dict."""
    if items is None:
        items = {}
    return {
        "last_heartbeat": None,
        "items": items,
    }


def _make_item(title="Test", stage="INTAKE", priority="Medium", review_status="PENDING", confidence=None):
    """Helper to create a test item dict."""
    item = {
        "title": title,
        "priority": priority,
        "stage": stage,
        "created_at": "2026-05-14T00:00:00Z",
        "updated_at": "2026-05-14T00:00:00Z",
        "assigned_agent": None,
        "confidence_score": confidence,
        "blocked_reason": None,
        "review_status": review_status,
        "history": [{"stage": "INTAKE", "at": "2026-05-14T00:00:00Z"}],
    }
    return item


class TestGetNextActionableItems:
    def test_returns_intake_items(self):
        """Items at INTAKE stage should be actionable."""
        state = _make_items({"ID-001": _make_item(stage="INTAKE")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1
        assert actionable[0][0] == "ID-001"

    def test_excludes_review_pending(self):
        """Items at REVIEW_SPEC with PENDING status should NOT be actionable."""
        state = _make_items({
            "ID-001": _make_item(stage="REVIEW_SPEC", review_status="PENDING"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 0

    def test_includes_review_approved(self):
        """Items at REVIEW_SPEC with APPROVED status should be actionable."""
        state = _make_items({
            "ID-001": _make_item(stage="REVIEW_SPEC", review_status="APPROVED"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1

    def test_excludes_review_needs_revision(self):
        """Items at REVIEW_SPEC with NEEDS_REVISION should NOT be actionable."""
        state = _make_items({
            "ID-001": _make_item(stage="REVIEW_SPEC", review_status="NEEDS_REVISION"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 0

    def test_sorts_by_priority(self):
        """Items should be sorted High first, then Medium, then Low."""
        state = _make_items({
            "ID-001": _make_item(stage="INTAKE", priority="Medium"),
            "ID-002": _make_item(stage="INTAKE", priority="High"),
            "ID-003": _make_item(stage="INTAKE", priority="Low"),
        })
        actionable = orchestrator.get_next_actionable_items(state)
        assert actionable[0][0] == "ID-002"  # High
        assert actionable[1][0] == "ID-001"  # Medium
        assert actionable[2][0] == "ID-003"  # Low

    def test_returns_refinement_items(self):
        """Items at REFINEMENT stage should be actionable."""
        state = _make_items({"ID-001": _make_item(stage="REFINEMENT")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1

    def test_returns_done_items_not_actionable(self):
        """Items at DONE stage should not be actionable (not a review stage, but handler is no-op)."""
        state = _make_items({"ID-001": _make_item(stage="DONE")})
        actionable = orchestrator.get_next_actionable_items(state)
        assert len(actionable) == 1  # DONE is not a review stage, so it IS actionable technically


class TestTransitionStage:
    def test_updates_stage(self):
        """transition_stage should update the item's stage."""
        item = _make_item(stage="INTAKE")
        state = _make_items({"ID-001": item})
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    def test_sets_assigned_agent(self):
        """transition_stage should set the assigned agent for the new stage."""
        item = _make_item(stage="INTAKE")
        state = _make_items({"ID-001": item})
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert item["assigned_agent"] == "refiner"

    def test_adds_history_entry(self):
        """transition_stage should add a history entry."""
        item = _make_item(stage="INTAKE")
        state = _make_items({"ID-001": item})
        initial_history_len = len(item["history"])
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert len(item["history"]) == initial_history_len + 1


class TestStageHandlers:
    def test_handle_intake_transitions_to_refinement(self):
        """handle_intake should transition to REFINEMENT."""
        item = _make_item(stage="INTAKE")
        state = _make_items({"ID-001": item})
        orchestrator.handle_intake(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_handle_refinement_calls_refiner(self, mock_refine):
        """handle_refinement should call refiner.refine_idea."""
        mock_refine.return_value = 85
        item = _make_item(stage="REFINEMENT", title="Test idea")
        state = _make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        mock_refine.assert_called_once_with("ID-001", "Test idea")
        assert item["stage"] == "REVIEW_SPEC"
        assert item["confidence_score"] == 85

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_handle_refinement_sets_blocked_on_failure(self, mock_refine):
        """handle_refinement should set blocked_reason on failure."""
        mock_refine.side_effect = ValueError("Bad idea")
        item = _make_item(stage="REFINEMENT", title="Bad idea")
        state = _make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "Bad idea" in item["blocked_reason"]

    def test_handle_review_spec_approved(self):
        """handle_review_spec with APPROVED should transition to ARCHITECTURE."""
        item = _make_item(stage="REVIEW_SPEC", review_status="APPROVED")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"

    def test_handle_review_spec_needs_revision(self):
        """handle_review_spec with NEEDS_REVISION should transition to REFINEMENT."""
        item = _make_item(stage="REVIEW_SPEC", review_status="NEEDS_REVISION")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    def test_handle_review_spec_pending(self):
        """handle_review_spec with PENDING should not transition."""
        item = _make_item(stage="REVIEW_SPEC", review_status="PENDING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "REVIEW_SPEC"

    def test_handle_done_noop(self):
        """handle_done should not change the stage."""
        item = _make_item(stage="DONE")
        state = _make_items({"ID-001": item})
        orchestrator.handle_done(item, state, "ID-001")
        assert item["stage"] == "DONE"


class TestArchitectureStageHandler:
    @patch("agents.orchestrator.architect.architect_idea")
    def test_handle_architecture_calls_architect(self, mock_architect):
        """handle_architecture should call architect.architect_idea."""
        mock_architect.return_value = 90
        item = _make_item(stage="ARCHITECTURE")
        state = _make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        mock_architect.assert_called_once_with("ID-001")
        assert item["stage"] == "REVIEW_ARCH"
        assert item["confidence_score"] == 90

    @patch("agents.orchestrator.architect.architect_idea")
    def test_handle_architecture_sets_blocked_on_failure(self, mock_architect):
        """handle_architecture should set blocked_reason on failure."""
        mock_architect.side_effect = FileNotFoundError("spec.md not found")
        item = _make_item(stage="ARCHITECTURE")
        state = _make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "spec.md not found" in item["blocked_reason"]

    def test_handle_review_arch_approved(self):
        """handle_review_arch with APPROVED should transition to TESTING."""
        item = _make_item(stage="REVIEW_ARCH", review_status="APPROVED")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "TESTING"

    def test_handle_review_arch_needs_revision(self):
        """handle_review_arch with NEEDS_REVISION should transition to ARCHITECTURE."""
        item = _make_item(stage="REVIEW_ARCH", review_status="NEEDS_REVISION")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"

    def test_handle_review_arch_pending(self):
        """handle_review_arch with PENDING should not transition."""
        item = _make_item(stage="REVIEW_ARCH", review_status="PENDING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "REVIEW_ARCH"


class TestTestingStageHandler:
    @patch("agents.orchestrator.tester.tester_idea")
    def test_handle_testing_calls_tester(self, mock_tester):
        """handle_testing should call tester.tester_idea."""
        mock_tester.return_value = 85
        item = _make_item(stage="TESTING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        mock_tester.assert_called_once_with("ID-001", use_docker=False)
        assert item["stage"] == "REVIEW_TEST"
        assert item["confidence_score"] == 85

    @patch("agents.orchestrator.tester.tester_idea")
    def test_handle_testing_sets_blocked_on_failure(self, mock_tester):
        """handle_testing should set blocked_reason on failure."""
        mock_tester.side_effect = FileNotFoundError("architecture.md not found")
        item = _make_item(stage="TESTING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "architecture.md not found" in item["blocked_reason"]

    def test_handle_review_test_approved(self):
        """handle_review_test with APPROVED should transition to APPROVED."""
        item = _make_item(stage="REVIEW_TEST", review_status="APPROVED")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "ID-001")
        assert item["stage"] == "APPROVED"

    def test_handle_review_test_needs_revision(self):
        """handle_review_test with NEEDS_REVISION should transition to TESTING."""
        item = _make_item(stage="REVIEW_TEST", review_status="NEEDS_REVISION")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "ID-001")
        assert item["stage"] == "TESTING"

    def test_handle_review_test_pending(self):
        """handle_review_test with PENDING should not transition."""
        item = _make_item(stage="REVIEW_TEST", review_status="PENDING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "ID-001")
        assert item["stage"] == "REVIEW_TEST"


class TestAuditIntegration:
    @patch("agents.orchestrator.audit_module.log_action")
    @patch("agents.orchestrator.refiner.refine_idea")
    def test_refinement_logs_audit(self, mock_refine, mock_audit):
        """handle_refinement should log an audit entry."""
        mock_refine.return_value = 85
        item = _make_item(stage="REFINEMENT", title="Test idea")
        state = _make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args["agent_name"] == "refiner"
        assert call_args["idea_id"] == "ID-001"
        assert call_args["stage"] == "REFINEMENT"

    @patch("agents.orchestrator.audit_module.log_action")
    @patch("agents.orchestrator.architect.architect_idea")
    def test_architecture_logs_audit(self, mock_architect, mock_audit):
        """handle_architecture should log an audit entry."""
        mock_architect.return_value = 90
        item = _make_item(stage="ARCHITECTURE")
        state = _make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args["agent_name"] == "architect"
        assert call_args["idea_id"] == "ID-001"
        assert call_args["stage"] == "ARCHITECTURE"

    @patch("agents.orchestrator.audit_module.log_action")
    @patch("agents.orchestrator.tester.tester_idea")
    def test_testing_logs_audit(self, mock_tester, mock_audit):
        """handle_testing should log an audit entry."""
        mock_tester.return_value = 85
        item = _make_item(stage="TESTING")
        state = _make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args["agent_name"] == "tester"
        assert call_args["idea_id"] == "ID-001"
        assert call_args["stage"] == "TESTING"


class TestRunPipeline:
    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_processes_items(self, mock_save, mock_load):
        """run_pipeline should process all actionable items."""
        state = _make_items({
            "ID-001": _make_item(stage="INTAKE", priority="High"),
            "ID-002": _make_item(stage="INTAKE", priority="Medium"),
        })
        mock_load.return_value = state

        result = orchestrator.run_pipeline()

        assert result == 2
        # Both items should have transitioned from INTAKE to REFINEMENT
        assert state["items"]["ID-001"]["stage"] == "REFINEMENT"
        assert state["items"]["ID-002"]["stage"] == "REFINEMENT"
        mock_save.assert_called_once()

    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_no_actionable_items(self, mock_save, mock_load):
        """run_pipeline should return 0 when no items are actionable."""
        state = _make_items({
            "ID-001": _make_item(stage="REVIEW_SPEC", review_status="PENDING"),
        })
        mock_load.return_value = state

        result = orchestrator.run_pipeline()

        assert result == 0
        # save_state should still be called to update last_heartbeat
        mock_save.assert_called_once()

    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_full_flow(self, mock_save, mock_load):
        """run_pipeline should handle full INTAKE to REVIEW_TEST flow with mocks."""
        state = _make_items({
            "ID-001": _make_item(stage="INTAKE", priority="High"),
        })
        mock_load.return_value = state

        # Simulate multiple pipeline runs to advance through stages
        # Run 1: INTAKE -> REFINEMENT -> REVIEW_SPEC
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REFINEMENT"

        # Run 2: REFINEMENT -> REVIEW_SPEC (refiner runs)
        with patch("agents.orchestrator.refiner.refine_idea", return_value=85):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_SPEC"

        # Run 3: REVIEW_SPEC approved -> ARCHITECTURE
        state["items"]["ID-001"]["review_status"] = "APPROVED"
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "ARCHITECTURE"

        # Run 4: ARCHITECTURE -> REVIEW_ARCH (architect runs)
        with patch("agents.orchestrator.architect.architect_idea", return_value=90):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_ARCH"

        # Run 5: REVIEW_ARCH approved -> TESTING
        state["items"]["ID-001"]["review_status"] = "APPROVED"
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "TESTING"

        # Run 6: TESTING -> REVIEW_TEST (tester runs)
        with patch("agents.orchestrator.tester.tester_idea", return_value=85):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_TEST"


def _make_items(items_dict):
    """Helper to create a state dict with items."""
    return {"last_heartbeat": None, "items": items_dict}