"""
Tests for Orchestrator stage transitions and pipeline runs.
"""
import pytest
from unittest.mock import patch
from agents import orchestrator
from tests.test_helpers import make_items, make_item

class TestTransitionStage:
    def test_updates_stage(self):
        """transition_stage should update the item's stage."""
        item = make_item(stage="INTAKE")
        state = make_items({"ID-001": item})
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    def test_sets_assigned_agent(self):
        """transition_stage should set the assigned agent for the new stage."""
        item = make_item(stage="INTAKE")
        state = make_items({"ID-001": item})
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert item["assigned_agent"] == "refiner"

    def test_adds_history_entry(self):
        """transition_stage should add a history entry."""
        item = make_item(stage="INTAKE")
        state = make_items({"ID-001": item})
        initial_history_len = len(item["history"])
        orchestrator.transition_stage(item, "REFINEMENT", state, "ID-001")
        assert len(item["history"]) == initial_history_len + 1

class TestRunPipeline:
    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_processes_items(self, mock_save, mock_load):
        """run_pipeline should process all actionable items."""
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority="High"),
            "ID-002": make_item(stage="INTAKE", priority="Medium"),
        })
        mock_load.return_value = state
        result = orchestrator.run_pipeline()
        assert result == 2
        assert state["items"]["ID-001"]["stage"] == "REFINEMENT"
        assert state["items"]["ID-002"]["stage"] == "REFINEMENT"
        mock_save.assert_called_once()

    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_no_actionable_items(self, mock_save, mock_load):
        """run_pipeline should return 0 when no items are actionable."""
        state = make_items({
            "ID-001": make_item(stage="REVIEW_SPEC", review_status="PENDING"),
        })
        mock_load.return_value = state
        result = orchestrator.run_pipeline()
        assert result == 0
        mock_save.assert_called_once()

    @patch("agents.orchestrator.state_module.load_state")
    @patch("agents.orchestrator.state_module.save_state")
    def test_run_pipeline_full_flow(self, mock_save, mock_load):
        """run_pipeline should handle full INTAKE to REVIEW_TEST flow with mocks."""
        state = make_items({
            "ID-001": make_item(stage="INTAKE", priority="High"),
        })
        mock_load.return_value = state
        
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REFINEMENT"
        with patch("agents.orchestrator.refiner.refine_idea", return_value=85):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_SPEC"
        state["items"]["ID-001"]["review_status"] = "APPROVED"
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "ARCHITECTURE"
        with patch("agents.orchestrator.architect.architect_idea", return_value=90):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_ARCH"
        state["items"]["ID-001"]["review_status"] = "APPROVED"
        orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "TESTING"
        with patch("agents.orchestrator.tester.tester_idea", return_value=85):
            orchestrator.run_pipeline()
        assert state["items"]["ID-001"]["stage"] == "REVIEW_TEST"
