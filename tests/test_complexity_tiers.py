"""
P4.1 — Complexity-tier stage-skip pipeline.

Covers:
  * ``next_stage()`` unit table (every stage × tier, plus sentinel/unknown
    fallbacks).
  * ``estimate_complexity()`` deterministic classifier.
  * ``handle_refinement`` complexity-set behavior (human override wins,
    ``"auto"`` defers to refiner, ``confidence_score`` stays ``int``).
  * Pipeline tier traversal (trivial never visits ARCHITECTURE/TESTING/APPROVED;
    simple never visits TESTING/APPROVED).
  * ``handle_executing`` failure fallback (``trivial`` → REVIEW_SPEC, not
    REVIEW_TEST).
  * Pydantic schema validation for ``complexity`` on both request models.
  * ``KanbanStateManager.create_item`` persists ``complexity``.
"""
import pytest
from unittest.mock import patch

from agents.constants import (
    PIPELINE_STAGES,
    TIER_STAGES,
    DEFAULT_COMPLEXITY,
    next_stage,
)
from agents import refiner, orchestrator
from tests.test_helpers import make_item, make_items


# ---------------------------------------------------------------------------
# next_stage() unit table
# ---------------------------------------------------------------------------

class TestNextStage:
    @pytest.mark.parametrize("tier", ["trivial", "simple", "complex"])
    def test_each_stage_advances_along_tier_path(self, tier):
        path = TIER_STAGES[tier]
        for i, stage in enumerate(path[:-1]):
            assert next_stage(stage, tier) == path[i + 1]

    @pytest.mark.parametrize("tier", ["trivial", "simple", "complex"])
    def test_terminal_stage_has_no_next(self, tier):
        assert next_stage(TIER_STAGES[tier][-1], tier) is None

    def test_unknown_current_returns_none(self):
        assert next_stage("NOPE", "complex") is None

    def test_complex_default_equals_full_pipeline(self):
        assert TIER_STAGES["complex"] == PIPELINE_STAGES
        # next_stage with None complexity walks the full pipeline.
        for i, stage in enumerate(PIPELINE_STAGES[:-1]):
            assert next_stage(stage, None) == PIPELINE_STAGES[i + 1]

    @pytest.mark.parametrize("sentinel", [None, "", "auto", "AUTO", "unknown"])
    def test_sentinel_or_unknown_complexity_falls_back_to_default(self, sentinel):
        # The fallback must reproduce the complex-tier successor for every stage.
        for i, stage in enumerate(PIPELINE_STAGES[:-1]):
            assert next_stage(stage, sentinel) == PIPELINE_STAGES[i + 1]
        assert next_stage(PIPELINE_STAGES[-1], sentinel) is None

    def test_complexity_is_case_insensitive(self):
        assert next_stage("INTAKE", "TRIVIAL") == next_stage("INTAKE", "trivial")


# ---------------------------------------------------------------------------
# estimate_complexity()
# ---------------------------------------------------------------------------

class TestEstimateComplexity:
    def test_empty_spec_is_complex(self):
        assert refiner.estimate_complexity("") == "complex"

    def test_short_spec_is_trivial_regardless_of_keywords(self):
        # Under 400 chars → trivial even if it mentions "auth".
        short = "Add a /health endpoint. " * 5
        assert len(short) < 400
        assert refiner.estimate_complexity(short) == "trivial"

    def test_trivial_keywords_in_longer_spec(self):
        spec = ("Add a health check endpoint and ping route. " * 30)  # >400 chars
        assert refiner.estimate_complexity(spec) == "trivial"

    def test_simple_keywords_without_complex(self):
        spec = ("Add a small cli helper script as a migration. " * 30)
        assert refiner.estimate_complexity(spec) == "simple"

    def test_complex_keywords_win_ties(self):
        # Both simple and complex keywords present → complex must win so we
        # never under-pipeline a security/distributed task.
        spec = ("Build an auth service and a migration script. " * 30)
        assert refiner.estimate_complexity(spec) == "complex"

    def test_long_spec_no_keywords_defaults_to_complex(self):
        spec = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 30
        assert refiner.estimate_complexity(spec) == "complex"

    def test_title_contributes_keywords(self):
        # Body alone is generic (→ complex), but a title mentioning "health"
        # trivial-classifies a long body via the title keyword.
        body = "Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 30
        assert refiner.estimate_complexity(body, title="health endpoint") == "trivial"


# ---------------------------------------------------------------------------
# handle_refinement — complexity-set + confidence regression
# ---------------------------------------------------------------------------

class TestRefinementComplexity:
    @patch("agents.orchestrator.refiner.refine_idea")
    def test_human_complexity_not_overwritten(self, mock_refine):
        mock_refine.return_value = 85
        item = make_item(stage="REFINEMENT", title="My idea")
        item["complexity"] = "trivial"           # explicit human override
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["complexity"] == "trivial"   # refiner did not clobber it
        # trivial path: REFINEMENT → REVIEW_SPEC
        assert item["stage"] == "REVIEW_SPEC"

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_auto_complexity_defers_to_refiner(self, mock_refine):
        mock_refine.return_value = 85
        item = make_item(stage="REFINEMENT", title="Add /health")
        item["complexity"] = "auto"              # UI sentinel → refiner decides
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        # No spec.md written by the mock → estimate_complexity("") → "complex"
        # (regression guard: estimate on empty spec, not a crash).
        assert item["complexity"] == "complex"

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_absent_complexity_defers_to_refiner(self, mock_refine):
        mock_refine.return_value = 90
        item = make_item(stage="REFINEMENT", title="Whatever")
        assert "complexity" not in item
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["complexity"] == DEFAULT_COMPLEXITY

    @patch("agents.orchestrator.refiner.refine_idea")
    def test_confidence_score_remains_int(self, mock_refine):
        # Regression guard against the tuple-return redesign mentioned in the
        # plan: refine_idea() must keep returning an int confidence.
        mock_refine.return_value = 72
        item = make_item(stage="REFINEMENT", title="x")
        state = make_items({"ID-001": item})
        orchestrator.handle_refinement(item, state, "ID-001")
        assert item["confidence_score"] == 72
        assert isinstance(item["confidence_score"], int)


# ---------------------------------------------------------------------------
# Tier traversal — skipped stages never get visited on forward progress
# ---------------------------------------------------------------------------

class TestTierTraversal:
    def _walk_forward(self, tier):
        """Advance an item from INTAKE following `_advance` (approved-review)
        and return the ordered list of stages it lands on."""
        item = make_item(stage="INTAKE", title="t")
        item["complexity"] = tier
        item["review_status"] = "APPROVED"   # auto-approve every review gate
        state = make_items({"ID-001": item})
        seen = []
        for _ in range(len(PIPELINE_STAGES) + 1):
            seen.append(item["stage"])
            if item["stage"] == "DONE":
                break
            stage = item["stage"]
            if stage.startswith("REVIEW_"):
                if stage == "REVIEW_SPEC":
                    orchestrator.handle_review_spec(item, state, "ID-001")
                elif stage == "REVIEW_ARCH":
                    orchestrator.handle_review_arch(item, state, "ID-001")
                else:
                    orchestrator.handle_review_test(item, state, "ID-001")
            elif stage == "INTAKE":
                orchestrator.handle_intake(item, state, "ID-001")
            elif stage == "REFINEMENT":
                # Mock the refiner so no file I/O happens; complexity already
                # set by the human, so the estimate branch is skipped.
                with patch("agents.orchestrator.refiner.refine_idea", return_value=80):
                    orchestrator.handle_refinement(item, state, "ID-001")
            elif stage == "ARCHITECTURE":
                with patch("agents.orchestrator.architect.architect_idea", return_value=80):
                    orchestrator.handle_architecture(item, state, "ID-001")
            elif stage == "TESTING":
                with patch("agents.orchestrator.tester.tester_idea", return_value=80):
                    orchestrator.handle_testing(item, state, "ID-001")
            elif stage == "APPROVED":
                orchestrator.handle_approved(item, state, "ID-001")
            elif stage == "EXECUTING":
                # Don't actually execute — patch the executor + the manager
                # that handle_executing reconstructs internally, then fake a
                # positive confidence so the item proceeds to DONE.
                from unittest.mock import MagicMock
                fake_sm = MagicMock()
                fake_sm.bindings.get_run_id_for_item.return_value = "run-1"
                with patch("api.workflow_state_manager.WorkflowStateManager",
                           return_value=fake_sm), \
                     patch("agents.executor.executor_idea", return_value=80):
                    orchestrator.handle_executing(item, state, "ID-001")
            else:
                break
        return seen

    def test_trivial_never_visits_architecture_testing_approved(self):
        seen = self._walk_forward("trivial")
        for skipped in ("ARCHITECTURE", "REVIEW_ARCH", "TESTING", "REVIEW_TEST", "APPROVED"):
            assert skipped not in seen, f"trivial item visited {skipped}: {seen}"
        assert "DONE" in seen

    def test_simple_never_visits_testing_approved(self):
        seen = self._walk_forward("simple")
        for skipped in ("TESTING", "REVIEW_TEST", "APPROVED"):
            assert skipped not in seen, f"simple item visited {skipped}: {seen}"
        # simple DOES visit ARCHITECTURE + REVIEW_ARCH.
        assert "ARCHITECTURE" in seen and "REVIEW_ARCH" in seen
        assert "DONE" in seen

    def test_complex_visits_every_stage(self):
        seen = self._walk_forward("complex")
        for stage in PIPELINE_STAGES:
            assert stage in seen, f"complex item skipped {stage}: {seen}"


# ---------------------------------------------------------------------------
# handle_executing failure fallback
# ---------------------------------------------------------------------------

class TestExecutorFallback:
    def _run_executing_with_confidence(self, tier, confidence):
        from unittest.mock import MagicMock
        item = make_item(stage="EXECUTING", title="t", confidence=None)
        item["complexity"] = tier
        state = make_items({"ID-001": item})
        fake_sm = MagicMock()
        fake_sm.bindings.get_run_id_for_item.return_value = "run-1"
        with patch("api.workflow_state_manager.WorkflowStateManager",
                   return_value=fake_sm), \
             patch("agents.executor.executor_idea", return_value=confidence):
            orchestrator.handle_executing(item, state, "ID-001")
        return item

    def test_trivial_failure_falls_back_to_review_spec(self):
        item = self._run_executing_with_confidence("trivial", 0)
        # REVIEW_TEST isn't in the trivial path → fallback must be REVIEW_SPEC.
        assert item["stage"] == "REVIEW_SPEC"
        assert item["stage"] != "REVIEW_TEST"

    def test_complex_failure_falls_back_to_review_test(self):
        item = self._run_executing_with_confidence("complex", 0)
        assert item["stage"] == "REVIEW_TEST"


# ---------------------------------------------------------------------------
# Pydantic schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_create_accepts_each_tier(self):
        from api.schemas import CreateItemRequest
        for tier in ("trivial", "simple", "complex"):
            req = CreateItemRequest(item_id="ID-1", title="t", complexity=tier)
            assert req.complexity == tier

    def test_create_accepts_auto_and_none(self):
        from api.schemas import CreateItemRequest
        assert CreateItemRequest(item_id="ID-1", title="t", complexity=None).complexity is None
        assert CreateItemRequest(item_id="ID-1", title="t", complexity="auto").complexity == "auto"

    def test_create_rejects_unknown_complexity(self):
        from api.schemas import CreateItemRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            CreateItemRequest(item_id="ID-1", title="t", complexity="runway")

    def test_update_accepts_tier_and_normalizes_case(self):
        from api.schemas import UpdateItemRequest
        assert UpdateItemRequest(complexity="SIMPLE").complexity == "simple"

    def test_update_rejects_unknown_complexity(self):
        from api.schemas import UpdateItemRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UpdateItemRequest(complexity="runway")


# ---------------------------------------------------------------------------
# KanbanStateManager.create_item persists complexity
# ---------------------------------------------------------------------------

class TestManagerPersistsComplexity:
    def test_create_item_carries_complexity(self, tmp_path):
        from api.managers.kanban_state_manager import KanbanStateManager
        base = tmp_path / "ai"
        base.mkdir()
        mgr = KanbanStateManager(str(base))
        assert mgr.create_item("ID-1", "Title", complexity="simple") is True
        item = mgr.get_item_details("ID-1")
        assert item is not None
        assert item["complexity"] == "simple"

    def test_create_item_default_complexity_is_none(self, tmp_path):
        from api.managers.kanban_state_manager import KanbanStateManager
        base = tmp_path / "ai"
        base.mkdir()
        mgr = KanbanStateManager(str(base))
        mgr.create_item("ID-2", "Title")
        assert mgr.get_item_details("ID-2")["complexity"] is None
