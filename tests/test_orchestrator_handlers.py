"""
Tests for the Orchestrator's individual stage handlers.
"""
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from agents import architect as architect_module
from agents import handlers as handlers_module
from agents import orchestrator
from agents import refiner as refiner_module
from agents import tester as tester_module
from tests.test_helpers import make_items, make_item


def _artifact_path(agent_module, item_id, name):
    return Path(agent_module.REQUIREMENTS_DIR, item_id, name)


def _write_artifact(agent_module, item_id, name, content):
    path = _artifact_path(agent_module, item_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path

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


# ---------------------------------------------------------------------------
# D3 (P2-1): hold at stage on agent failure or stub reply
# ---------------------------------------------------------------------------

STUB_TEXT = "[stub response — no provider reachable]"


class TestHoldAtStageOnFailure:
    """A raising agent keeps the item at its stage with blocked_reason set."""

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_refiner_failure_holds_at_refinement(self, mock_refine):
        mock_refine.side_effect = ValueError("provider down")
        item = make_item(stage="REFINEMENT", title="T")
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"
        assert "provider down" in item["blocked_reason"]
        assert "Refiner failed" in item["blocked_reason"]

    @patch("agents.orchestrator.architect.architect_idea")
    def test_architect_failure_holds_at_architecture(self, mock_architect):
        mock_architect.side_effect = RuntimeError("no spec")
        item = make_item(stage="ARCHITECTURE")
        state = make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"
        assert "no spec" in item["blocked_reason"]
        assert "Architect failed" in item["blocked_reason"]

    @patch("agents.orchestrator.tester.tester_idea")
    def test_tester_failure_holds_at_testing(self, mock_tester):
        mock_tester.side_effect = RuntimeError("no architecture")
        item = make_item(stage="TESTING")
        state = make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        assert item["stage"] == "TESTING"
        assert "no architecture" in item["blocked_reason"]
        assert "Tester failed" in item["blocked_reason"]


class TestHoldAtStageOnStubReply:
    """A stub-text reply (LLMClient.is_stub) is a failure: no artifact, no advance."""

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_refiner_stub_holds_and_writes_no_spec(self, mock_refine):
        def stub_refine(idea_id, title):
            _write_artifact(refiner_module, idea_id, "spec.md", STUB_TEXT)
            return 10

        mock_refine.side_effect = stub_refine
        item = make_item(stage="REFINEMENT", title="T")
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["stage"] == "REFINEMENT"
        assert "stub" in item["blocked_reason"].lower()
        assert not _artifact_path(refiner_module, "ID-001", "spec.md").exists()

    @patch("agents.orchestrator.architect.architect_idea")
    def test_architect_stub_holds_and_writes_no_architecture(self, mock_architect):
        def stub_architect(idea_id):
            _write_artifact(architect_module, idea_id, "architecture.md", STUB_TEXT)
            return 10

        mock_architect.side_effect = stub_architect
        item = make_item(stage="ARCHITECTURE")
        state = make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        assert item["stage"] == "ARCHITECTURE"
        assert "stub" in item["blocked_reason"].lower()
        assert not _artifact_path(architect_module, "ID-001", "architecture.md").exists()

    @patch("agents.orchestrator.tester.tester_idea")
    def test_tester_stub_holds_and_writes_no_tests(self, mock_tester):
        def stub_tester(idea_id, use_docker=False):
            _write_artifact(tester_module, idea_id, "tests.md", STUB_TEXT)
            return 10

        mock_tester.side_effect = stub_tester
        item = make_item(stage="TESTING")
        state = make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        assert item["stage"] == "TESTING"
        assert "stub" in item["blocked_reason"].lower()
        assert not _artifact_path(tester_module, "ID-001", "tests.md").exists()

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_a_real_artifact_is_not_treated_as_stub(self, mock_refine):
        def real_refine(idea_id, title):
            _write_artifact(refiner_module, idea_id, "spec.md", "# Specification for ID-001\n\n## Requirements\n- do the thing\n" * 20)
            return 85

        mock_refine.side_effect = real_refine
        item = make_item(stage="REFINEMENT", title="T")
        item["complexity"] = "complex"  # skip the estimate branch
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["stage"] == "REVIEW_SPEC"
        assert _artifact_path(refiner_module, "ID-001", "spec.md").exists()


class TestSuccessClearsBlockedReason:
    """A later successful run clears a previous blocked_reason (D3)."""

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_refiner_success_clears_reason(self, mock_refine):
        mock_refine.return_value = 85
        item = make_item(stage="REFINEMENT", title="T")
        item["blocked_reason"] = "Refiner failed: earlier outage"
        item["complexity"] = "complex"
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["stage"] == "REVIEW_SPEC"
        assert not item.get("blocked_reason")

    @patch("agents.orchestrator.architect.architect_idea")
    def test_architect_success_clears_reason(self, mock_architect):
        mock_architect.return_value = 90
        item = make_item(stage="ARCHITECTURE")
        item["blocked_reason"] = "Architect failed: earlier outage"
        state = make_items({"ID-001": item})
        orchestrator.handle_architecture(item, state, "ID-001")
        assert item["stage"] == "REVIEW_ARCH"
        assert not item.get("blocked_reason")

    @patch("agents.orchestrator.tester.tester_idea")
    def test_tester_success_clears_reason(self, mock_tester):
        mock_tester.return_value = 85
        item = make_item(stage="TESTING")
        item["blocked_reason"] = "Tester failed: earlier outage"
        state = make_items({"ID-001": item})
        orchestrator.handle_testing(item, state, "ID-001")
        assert item["stage"] == "REVIEW_TEST"
        assert not item.get("blocked_reason")


# ---------------------------------------------------------------------------
# D4 (P2-2): run the executor without a bound workflow run
# ---------------------------------------------------------------------------

class TestExecutingWithoutBoundRun:
    """Unbound EXECUTING items run the agent executor directly (D4)."""

    def _executing_item(self, mode=None):
        item = make_item(stage="EXECUTING", title="t", confidence=None)
        item["complexity"] = "complex"
        if mode:
            item["execution_policy"] = {"mode": mode}
        return item

    def test_unbound_success_reaches_done(self):
        item = self._executing_item()
        state = make_items({"ID-001": item})
        with patch("agents.executor.executor_idea", return_value=90) as ex:
            orchestrator.handle_executing(item, state, "ID-001")
        assert item["stage"] == "DONE"
        assert item["confidence_score"] == 90
        # No binding exists, so the executor ran under the synthetic per-item id.
        assert ex.call_args[0][0] == "ID-001"
        assert ex.call_args[0][2] == "pipeline-ID-001"

    def test_unbound_failure_goes_to_tier_aware_fallback(self):
        for tier, expected in (("complex", "REVIEW_TEST"), ("trivial", "REVIEW_SPEC")):
            item = self._executing_item()
            item["complexity"] = tier
            state = make_items({"ID-001": item})
            with patch("agents.executor.executor_idea", return_value=0):
                orchestrator.handle_executing(item, state, "ID-001")
            assert item["stage"] == expected, tier
            assert not item.get("blocked_reason")  # fallback, not a block

    def test_unbound_inline_success_reaches_done(self):
        item = self._executing_item(mode="INLINE")
        state = make_items({"ID-001": item})
        with patch("agents.executor.executor_idea", return_value="inline-result") as ex:
            orchestrator.handle_executing(item, state, "ID-001")
        assert item["stage"] == "DONE"
        assert item["inline_output"] == "inline-result"
        assert ex.call_args[0][2] == "pipeline-ID-001"

    def test_bound_run_still_uses_the_run_path(self):
        from api.workflow_state_manager import WorkflowStateManager

        # Create a real binding on the same (tmp) data dir the handler uses.
        sm = WorkflowStateManager(handlers_module.DATA_DIR)
        sm.bindings.bind_run_to_item("run-42", "ID-001")

        item = self._executing_item()
        state = make_items({"ID-001": item})
        with patch("agents.executor.executor_idea", return_value=90) as ex:
            orchestrator.handle_executing(item, state, "ID-001")
        assert item["stage"] == "DONE"
        assert ex.call_args[0][2] == "run-42"

    def test_unbound_failure_with_exception_sets_blocked_reason(self):
        """An executor exception still sets blocked_reason and uses the fallback."""
        item = self._executing_item()
        state = make_items({"ID-001": item})
        with patch("agents.executor.executor_idea", side_effect=RuntimeError("boom")):
            orchestrator.handle_executing(item, state, "ID-001")
        assert item["stage"] == "REVIEW_TEST"
        assert "boom" in item["blocked_reason"]

    def test_mocked_state_manager_without_binding_also_runs(self):
        """The unbound path works through a mocked WorkflowStateManager too."""
        fake_sm = MagicMock()
        fake_sm.bindings.get_run_id_for_item.return_value = None
        item = self._executing_item()
        state = make_items({"ID-001": item})
        with patch("api.workflow_state_manager.WorkflowStateManager", return_value=fake_sm), \
             patch("agents.executor.executor_idea", return_value=80) as ex:
            orchestrator.handle_executing(item, state, "ID-001")
        assert item["stage"] == "DONE"
        assert ex.call_args[0][2] == "pipeline-ID-001"
