"""
Tests for the Orchestrator's individual stage handlers.
"""
import pytest
from unittest.mock import patch
from agents import orchestrator
from tests.test_helpers import make_items, make_item

class TestStageHandlers:
    def test_handle_intake_transitions_to_refinement(self):
        item = make_item(stage="INTAKE")
        state = make_items({"ID-001": item})
        orchestrator.handle_intake(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_handle_refinement_calls_refiner(self, mock_refine):
        mock_refine.return_value = 85
        item = make_item(stage="REFINEMENT", title="Test idea")
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        mock_refine.assert_called_once_with("ID-001", "Test idea")
        assert item["stage"] == "REVIEW_SPEC"
        assert item["confidence_score"] == 85

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_handle_refinement_sets_blocked_on_failure(self, mock_refine):
        mock_refine.side_effect = ValueError("Bad idea")
        item = make_item(stage="REFINEMENT", title="Bad idea")
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "Bad idea" in item["blocked_reason"]

    def test_handle_review_spec_approved(self):
        item = make_item(stage="REVIEW_SPEC", review_status="APPROVED")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"

    def test_handle_review_spec_needs_revision(self):
        item = make_item(stage="REVIEW_SPEC", review_status="NEEDS_REVISION")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"

    def test_handle_review_spec_pending(self):
        item = make_item(stage="REVIEW_SPEC", review_status="PENDING")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_spec(item, state, "ID-001")
        assert item["stage"] == "REVIEW_SPEC"

    def test_handle_done_noop(self):
        item = make_item(stage="DONE")
        state = make_items({"ID-001": item})
        orchestrator.handle_done(item, state, "ID-001")
        assert item["stage"] == "DONE"

class TestArchitectureStageHandler:
    @patch("agents.orchestrator.architect.architect_idea")
    def test_handle_architecture_calls_architect(self, mock_architect):
        mock_architect.return_value = 90
        item = make_item(stage="ARCHITECTURE")
        state = make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        mock_architect.assert_called_once_with("ID-001")
        assert item["stage"] == "REVIEW_ARCH"
        assert item["confidence_score"] == 90

    @patch("agents.orchestrator.architect.architect_idea")
    def test_handle_architecture_sets_blocked_on_failure(self, mock_architect):
        mock_architect.side_effect = FileNotFoundError("spec.md not found")
        item = make_item(stage="ARCHITECTURE")
        state = make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "spec.md not found" in item["blocked_reason"]

    def test_handle_review_arch_approved(self):
        item = make_item(stage="REVIEW_ARCH", review_status="APPROVED")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "TESTING"

    def test_handle_review_arch_needs_revision(self):
        item = make_item(stage="REVIEW_ARCH", review_status="NEEDS_REVISION")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"

    def test_handle_review_arch_pending(self):
        item = make_item(stage="REVIEW_ARCH", review_status="PENDING")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_arch(item, state, "ID-001")
        assert item["stage"] == "REVIEW_ARCH"

class TestTestingStageHandler:
    @patch("agents.orchestrator.tester.tester_idea")
    def test_handle_testing_calls_tester(self, mock_tester):
        mock_tester.return_value = 85
        item = make_item(stage="TESTING")
        state = make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        mock_tester.assert_called_once_with("ID-001", use_docker=False)
        assert item["stage"] == "REVIEW_TEST"
        assert item["confidence_score"] == 85

    @patch("agents.orchestrator.tester.tester_idea")
    def test_handle_testing_sets_blocked_on_failure(self, mock_tester):
        mock_tester.side_effect = FileNotFoundError("architecture.md not found")
        item = make_item(stage="TESTING")
        state = make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        assert item["blocked_reason"] is not None
        assert "architecture.md not found" in item["blocked_reason"]

    def test_handle_review_test_approved(self):
        item = make_item(stage="REVIEW_TEST", review_status="APPROVED")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "APPROVED")
        assert item["stage"] == "APPROVED"

    def test_handle_review_test_needs_revision(self):
        item = make_item(stage="REVIEW_TEST", review_status="NEEDS_REVISION")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "TESTING")
        assert item["stage"] == "TESTING"

    def test_handle_review_test_pending(self):
        item = make_item(stage="REVIEW_TEST", review_status="PENDING")
        state = make_items({"ID-001": item})
        orchestrator.handle_review_test(item, state, "REVIEW_TEST")
        assert item["stage"] == "REVIEW_TEST"
