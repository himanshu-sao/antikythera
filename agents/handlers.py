import logging
from pathlib import Path
from agents import refiner, architect, tester, audit as audit_module
from agents import logger as task_logger
from agents.constants import REVIEW_STAGES, TIER_STAGES, DEFAULT_COMPLEXITY
from agents.constants import next_stage

logger = logging.getLogger(__name__)

class StageHandler:
    """
    Contains the business logic for what happens during each pipeline stage.
    This class is called by the Orchestrator.
    """
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def _advance(self, item, state, item_id):
        """Move to the next stage for this item's complexity tier (DONE if none).

        P4.1: forward progress is tier-aware. Skipped columns simply stay
        empty for that item — ``next_stage`` returns the tier-specific
        successor (or ``None`` for terminal/unknown). This replaces the
        hard-coded ``transition_stage(item, "<NEXT>", ...)`` forward calls.
        """
        current = item.get("stage", "INTAKE")
        nxt = next_stage(current, item.get("complexity"))
        self.orchestrator.transition_stage(item, nxt or "DONE", state, item_id)

    def handle_intake(self, item, state, item_id):
        logger.info("Processing %s at INTAKE stage", item_id)
        task_logger.get_logger(item_id).info("orchestrator", "INTAKE_START", f"Beginning intake process for {item_id}")
        self._advance(item, state, item_id)

    def handle_refinement(self, item, state, item_id):
        logger.info("Processing %s at REFINEMENT stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "REFINEMENT_START", f"Starting refinement for {item_id}")

        title = item.get("title", "Untitled")
        try:
            confidence = refiner.refine_idea(item_id, title)
            item["confidence_score"] = confidence
            logger.info("Refiner completed for %s with confidence %d", item_id, confidence)
            t_logger.info("refiner", "REFINEMENT_COMPLETE", f"Refinement completed with confidence {confidence}", {"confidence": confidence})

            audit_module.log_action(
                agent_name="refiner",
                idea_id=item_id,
                stage="REFINEMENT",
                action="Generated spec.md from one-liner",
                inputs=f"Title: {title}",
                outputs=f"requirements/{item_id}/spec.md (confidence: {confidence})",
            )
        except Exception as e:
            logger.error("Refiner failed for %s: %s", item_id, str(e))
            t_logger.error("refiner", "REFINEMENT_FAILED", str(e))
            item["blocked_reason"] = f"Refiner failed: {str(e)}"

        # P4.1: classify complexity at REFINEMENT, but only when the human
        # hasn't already set it (an explicit ``complexity`` at create-time, or
        # a later override, always wins). ``"auto"`` is the UI's "let the
        # refiner decide" sentinel → treat as unset. We reuse the spec text the
        # Refiner just wrote; no extra LLM call. The spec read is best-effort:
        # ``refine_idea`` may be mocked in tests (skipping the write), in which
        # case we fall back to the default tier rather than crashing.
        if not item.get("complexity") or item.get("complexity") == "auto":
            try:
                spec_path = Path(refiner.REQUIREMENTS_DIR, item_id, "spec.md")
                spec = spec_path.read_text() if spec_path.exists() else ""
                item["complexity"] = refiner.estimate_complexity(spec, title=title)
            except Exception as ce:
                logger.warning("Complexity estimate failed for %s: %s", item_id, ce)
                item["complexity"] = DEFAULT_COMPLEXITY

        self._advance(item, state, item_id)

    def handle_review_spec(self, item, state, item_id):
        logger.info("Processing %s at REVIEW_SPEC stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            logger.info("%s review approved, transitioning to ARCHITECTURE", item_id)
            self._advance(item, state, item_id)
        elif review_status == "NEEDS_REVISION":
            logger.info("%s needs revision, transitioning back to REFINEMENT", item_id)
            self.orchestrator.transition_stage(item, "REFINEMENT", state, item_id)
        else:
            logger.info("%s review pending, waiting for owner", item_id)

    def handle_architecture(self, item, state, item_id):
        logger.info("Processing %s at ARCHITECTURE stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "ARCHITECTURE_START", f"Starting architecture design for {item_id}")

        try:
            confidence = architect.architect_idea(item_id)
            item["confidence_score"] = confidence
            logger.info("Architect completed for %s with confidence %d", item_id, confidence)
            t_logger.info("architect", "ARCHITECTURE_COMPLETE", f"Architecture completed with confidence {confidence}", {"confidence": confidence})

            audit_module.log_action(
                agent_name="architect",
                idea_id=item_id,
                stage="ARCHITECTURE",
                action="Generated architecture.md from spec.md",
                inputs=f"requirements/{item_id}/spec.md, brain/patterns.md",
                outputs=f"requirements/{item_id}/architecture.md (confidence: {confidence})",
            )
        except Exception as e:
            logger.error("Architect failed for %s: %s", item_id, str(e))
            t_logger.error("architect", "ARCHITECTURE_FAILED", str(e))
            item["blocked_reason"] = f"Architect failed: {str(e)}"
        
        self._advance(item, state, item_id)

    def handle_review_arch(self, item, state, item_id):
        logger.info("Processing %s at REVIEW_ARCH stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            logger.info("%s architecture review approved, transitioning to TESTING", item_id)
            self._advance(item, state, item_id)
        elif review_status == "NEEDS_REVISION":
            logger.info("%s architecture needs revision, transitioning back to ARCHITECTURE", item_id)
            self.orchestrator.transition_stage(item, "ARCHITECTURE", state, item_id)
        else:
            logger.info("%s architecture review pending, waiting for owner", item_id)

    def handle_testing(self, item, state, item_id):
        logger.info("Processing %s at TESTING stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "TESTING_START", f"Starting verification for {item_id}")

        try:
            confidence = tester.tester_idea(item_id, use_docker=False)
            item["confidence_score"] = confidence
            logger.info("Tester completed for %s with confidence %d", item_id, confidence)
            t_logger.info("tester", "TESTING_COMPLETE", f"Testing completed with confidence {confidence}", {"confidence": confidence})

            audit_module.log_action(
                agent_name="tester",
                idea_id=item_id,
                stage="TESTING",
                action="Generated tests.md from spec.md and architecture.md",
                inputs=f"requirements/{item_id}/spec.md, requirements/{item_id}/architecture.md",
                outputs=f"requirements/{item_id}/tests.md (confidence: {confidence})",
            )
        except Exception as e:
            logger.error("Tester failed for %s: %s", item_id, str(e))
            t_logger.error("tester", "TESTING_FAILED", str(e))
            item["blocked_reason"] = f"Tester failed: {str(e)}"

        self._advance(item, state, item_id)

    def handle_review_test(self, item, state, item_id):
        logger.info("Processing %s at REVIEW_TEST stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            logger.info("%s test review approved, transitioning to APPROVED", item_id)
            self._advance(item, state, item_id)
        elif review_status == "NEEDS_REVISION":
            logger.info("%s tests need revision, transitioning back to TESTING", item_id)
            self.orchestrator.transition_stage(item, "TESTING", state, item_id)
        else:
            logger.info("%s test review pending, waiting for owner", item_id)

    def handle_approved(self, item, state, item_id):
        logger.info("Processing %s at APPROVED stage", item_id)
        self._advance(item, state, item_id)

    def handle_executing(self, item, state, item_id):
        logger.info("Processing %s at EXECUTING stage", item_id)
        import os
        from api.managers.run_manager import RunManager
        from api.workflow_state_manager import WorkflowStateManager
        
        # In a real production environment, we'd get this via dependency injection.
        # For now, we reconstruct the manager to access the run_manager.
        # The base_dir is 'automation-ideas' (as configured in api/main.py)
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "automation-ideas"))
        state_manager = WorkflowStateManager(base_dir)
        run_manager = state_manager.runs

        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "EXECUTION_START", f"Starting implementation for {item_id}")

        confidence = 0
        try:
            execution_mode = item.get('execution_policy', {}).get('mode', 'ENGINEERING')
            if execution_mode == 'INLINE':
                logger.info("Executing INLINE task for %s", item_id)
                from agents import executor
                
                # Get the current run_id for this item
                run_id = state_manager.bindings.get_run_id_for_item(item_id)
                if not run_id:
                    raise RuntimeError(f"No active run found for item {item_id}")
                
                result = executor.executor_idea(item_id, run_manager, run_id)
                item['inline_output'] = result
                from agents import state as state_module
                state_module.save_state(state)
                self.orchestrator.transition_stage(item, 'DONE', state, item_id)
                t_logger.info("executor", "EXECUTION_COMPLETE_INLINE", f"Inline execution successful")
                return
            
            from agents import executor
            
            # Get the current run_id for this item
            run_id = state_manager.bindings.get_run_id_for_item(item_id)
            if not run_id:
                raise RuntimeError(f"No active run found for item {item_id}")

            confidence = executor.executor_idea(item_id, run_manager, run_id)
            item["confidence_score"] = confidence
            logger.info("Executor completed for %s with confidence %d", item_id, confidence)
            t_logger.info("executor", "EXECUTION_COMPLETE", f"Implementation completed with confidence {confidence}", {"confidence": confidence})

            audit_module.log_action(
                agent_name="executor",
                idea_id=item_id,
                stage="EXECUTING",
                action="Implemented requirements and verified via tests",
                inputs=f"requirements/{item_id}/spec.md, requirements/{item_id}/architecture.md, requirements/{item_id}/tests.md",
                outputs=f"requirements/{item_id}/execution_report.md (confidence: {confidence})",
            )
        except Exception as e:
            logger.error("Executor failed for %s: %s", item_id, str(e))
            t_logger.error("executor", "EXECUTION_FAILED", str(e))
            item["blocked_reason"] = f"Executor failed: {str(e)}"
        
        if confidence > 0:
            self.orchestrator.transition_stage(item, "DONE", state, item_id)
        else:
            # P4.1: REVIEW_TEST only exists for the `complex` tier. For
            # trivial/simple items route the failure back to REVIEW_SPEC — the
            # one review gate present in every tier — so a human can decide.
            fallback = "REVIEW_TEST" if next_stage("REVIEW_TEST", item.get("complexity")) else "REVIEW_SPEC"
            self.orchestrator.transition_stage(item, fallback, state, item_id)

    def handle_done(self, item, state, item_id):
        logger.info("%s is already DONE, skipping", item_id)
        task_logger.get_logger(item_id).info("orchestrator", "PIPELINE_END", f"Task {item_id} completed")
