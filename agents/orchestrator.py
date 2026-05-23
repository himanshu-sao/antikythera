import logging
import yaml
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from agents import state as state_module
from agents import refiner
from agents import architect
from agents import tester
from agents import audit as audit_module
from agents import telegram
from agents import logger as task_logger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# All pipeline stages in order
PIPELINE_STAGES = [
    "INTAKE",
    "REFINEMENT",
    "REVIEW_SPEC",
    "ARCHITECTURE",
    "REVIEW_ARCH",
    "TESTING",
    "REVIEW_TEST",
    "APPROVED",
    "EXECUTING",
    "DONE",
]

# Stages that block on owner review
REVIEW_STAGES = {"REVIEW_SPEC", "REVIEW_ARCH", "REVIEW_TEST"}

# Agent responsible for each non-review stage
STAGE_AGENTS = {
    "INTAKE": None,
    "REFINEMENT": "refiner",
    "REVIEW_SPEC": None,
    "ARCHITECTURE": "architect",
    "REVIEW_ARCH": None,
    "TESTING": "tester",
    "REVIEW_TEST": None,
    "APPROVED": None,
    "EXECUTING": "executor",
    "DONE": None,
}

class Orchestrator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_next_actionable_items(self, state):
        items = state.get("items", {})
        actionable = []
        for item_id, item in items.items():
            stage = item.get("stage", "INTAKE")
            if stage in REVIEW_STAGES:
                review_status = item.get("review_status", "PENDING")
                if review_status != "APPROVED":
                    continue
            actionable.append((item_id, item))
        
        priority_order = {"High": 0, "Medium": 1, "Low": 2}
        actionable.sort(key=lambda x: priority_order.get(x[1].get("priority", "Medium"), 99))
        return actionable

    def transition_stage(self, item, new_stage, state, item_id=None):
        old_stage = item.get("stage", "INTAKE")
        item["stage"] = new_stage
        agent = STAGE_AGENTS.get(new_stage)
        if agent:
            item["assigned_agent"] = agent
        else:
            item["assigned_agent"] = None

        if item_id:
            state_module.add_history_entry(state, item_id, new_stage, agent=agent)
            
            # Task Logging Integration
            try:
                t_logger = task_logger.get_logger(item_id)
                t_logger.info(agent or "orchestrator", "STAGE_TRANSITION", f"Moved from {old_stage} to {new_stage}")
            except Exception as e:
                self.logger.error("Failed to log stage transition for %s: %s", item_id, str(e))

            try:
                with open("config.yaml", "r") as f:
                    config = yaml.safe_load(f)
                tg = telegram.TelegramHandler(config)
                if new_stage in REVIEW_STAGES or new_stage == "DONE":
                    tg.send_notification(
                        item_id=item_id,
                        stage=new_stage,
                        title=item.get("title", "Untitled"),
                        confidence=item.get("confidence_score")
                    )
            except Exception as e:
                self.logger.error("Failed to send Telegram notification for %s: %s", item_id, str(e))

        self.logger.info("Transitioned %s: %s -> %s (agent: %s)", item_id or "?", old_stage, new_stage, agent or "none")

    def handle_intake(self, item, state, item_id):
        self.logger.info("Processing %s at INTAKE stage", item_id)
        
        # Task Logging
        task_logger.get_logger(item_id).info("orchestrator", "INTAKE_START", f"Beginning intake process for {item_id}")
        
        self.transition_stage(item, "REFINEMENT", state, item_id)

    def handle_refinement(self, item, state, item_id):
        self.logger.info("Processing %s at REFINEMENT stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "REFINEMENT_START", f"Starting refinement for {item_id}")

        title = item.get("title", "Untitled")
        try:
            confidence = refiner.refine_idea(item_id, title)
            item["confidence_score"] = confidence
            self.logger.info("Refiner completed for %s with confidence %d", item_id, confidence)
            
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
            self.logger.error("Refiner failed for %s: %s", item_id, str(e))
            t_logger.error("refiner", "REFINEMENT_FAILED", str(e))
            item["blocked_reason"] = f"Refiner failed: {str(e)}"
        self.transition_stage(item, "REVIEW_SPEC", state, item_id)

    def handle_review_spec(self, item, state, item_id):
        self.logger.info("Processing %s at REVIEW_SPEC stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            self.logger.info("%s review approved, transitioning to ARCHITECTURE", item_id)
            self.transition_stage(item, "ARCHITECTURE", state, item_id)
        elif review_status == "NEEDS_REVISION":
            self.logger.info("%s needs revision, transitioning back to REFINEMENT", item_id)
            self.transition_stage(item, "REFINEMENT", state, item_id)
        else:
            self.logger.info("%s review pending, waiting for owner", item_id)

    def handle_architecture(self, item, state, item_id):
        self.logger.info("Processing %s at ARCHITECTURE stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "ARCHITECTURE_START", f"Starting architecture design for {item_id}")

        try:
            confidence = architect.architect_idea(item_id)
            item["confidence_score"] = confidence
            self.logger.info("Architect completed for %s with confidence %d", item_id, confidence)
            
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
            self.logger.error("Architect failed for %s: %s", item_id, str(e))
            t_logger.error("architect", "ARCHITECTURE_FAILED", str(e))
            item["blocked_reason"] = f"Architect failed: {str(e)}"
        self.transition_stage(item, "REVIEW_ARCH", state, item_id)

    def handle_review_arch(self, item, state, item_id):
        self.logger.info("Processing %s at REVIEW_ARCH stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            self.logger.info("%s architecture review approved, transitioning to TESTING", item_id)
            self.transition_stage(item, "TESTING", state, item_id)
        elif review_status == "NEEDS_REVISION":
            self.logger.info("%s architecture needs revision, transitioning back to ARCHITECTURE", item_id)
            self.transition_stage(item, "ARCHITECTURE", state, item_id)
        else:
            self.logger.info("%s architecture review pending, waiting for owner", item_id)

    def handle_testing(self, item, state, item_id):
        self.logger.info("Processing %s at TESTING stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "TESTING_START", f"Starting verification for {item_id}")

        try:
            confidence = tester.tester_idea(item_id, use_docker=False)
            item["confidence_score"] = confidence
            self.logger.info("Tester completed for %s with confidence %d", item_id, confidence)
            
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
            self.logger.error("Tester failed for %s: %s", item_id, str(e))
            t_logger.error("tester", "TESTING_FAILED", str(e))
            item["blocked_reason"] = f"Tester failed: {str(e)}"
        self.transition_stage(item, "REVIEW_TEST", state, item_id)

    def handle_review_test(self, item, state, item_id):
        self.logger.info("Processing %s at REVIEW_TEST stage", item_id)
        review_status = item.get("review_status", "PENDING")
        if review_status == "APPROVED":
            self.logger.info("%s test review approved, transitioning to APPROVED", item_id)
            self.transition_stage(item, "APPROVED", state, item_id)
        elif review_status == "NEEDS_REVISION":
            self.logger.info("%s tests need revision, transitioning back to TESTING", item_id)
            self.transition_stage(item, "TESTING", state, item_id)
        else:
            self.logger.info("%s test review pending, waiting for owner", item_id)

    def handle_approved(self, item, state, item_id):
        self.logger.info("Processing %s at APPROVED stage", item_id)
        self.transition_stage(item, "EXECUTING", state, item_id)

    def handle_executing(self, item, state, item_id):
        self.logger.info("Processing %s at EXECUTING stage", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "EXECUTION_START", f"Starting implementation for {item_id}")

        confidence = 0
        try:
            # Check for INLINE execution mode
            execution_mode = item.get('execution_policy', {}).get('mode', 'ENGINEERING')
            if execution_mode == 'INLINE':
                self.logger.info("Executing INLINE task for %s", item_id)
                from agents import executor
                result = executor.executor_idea(item_id)
                # Instead of writing files, we update the state directly
                item['inline_output'] = result
                from agents import state as state_module
                state_module.save_state(state)
                self.transition_stage(item, 'DONE', state, item_id)
                t_logger.info("executor", "EXECUTION_COMPLETE_INLINE", f"Inline execution successful")
                return
            
            from agents import executor
            confidence = executor.executor_idea(item_id)
            item["confidence_score"] = confidence
            self.logger.info("Executor completed for %s with confidence %d", item_id, confidence)
            
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
            self.logger.error("Executor failed for %s: %s", item_id, str(e))
            t_logger.error("executor", "EXECUTION_FAILED", str(e))
            item["blocked_reason"] = f"Executor failed: {str(e)}"
        
        if confidence > 0:
            self.transition_stage(item, "DONE", state, item_id)
        else:
            self.transition_stage(item, "REVIEW_TEST", state, item_id)

    def handle_done(self, item, state, item_id):
        self.logger.info("%s is already DONE, skipping", item_id)
        t_logger = task_logger.get_logger(item_id)
        t_logger.info("orchestrator", "PIPELINE_END", f"Task {item_id} completed")

    def promote_artifact_to_pattern(self, item_id, artifact_name, content):
        """
        Orchestrates the extraction of patterns from a successful artifact.
        """
        self.logger.info("Promoting %s/%s to patterns for %s", artifact_name, item_id, item_id)
        try:
            from agents import memory
            success = memory.extract_pattern_from_content(item_id, artifact_name, content)
            if success:
                self.logger.info("Successfully promoted %s/%s to patterns", artifact_name, item_id)
                return True
            else:
                self.logger.error("Memory agent failed to extract pattern for %s", item_id)
                return False
        except Exception as e:
            self.logger.error("Pattern promotion failed for %s: %s", item_id, str(e))
            return False

    def process_item(self, item, state, item_id):
        stage = item.get("stage", "INTAKE")
        handler_name = STAGE_HANDLERS.get(stage)
        if handler_name:
            method = getattr(self, handler_name)
            method(item, state, item_id)
        else:
            self.logger.warning("No handler for stage %s on item %s", stage, item_id)

    def run_pipeline(self):
        self.logger.info("Pipeline run starting")
        state = state_module.load_state()
        actionable = self.get_next_actionable_items(state)

        processed = 0
        for item_id, item in actionable:
            self.logger.info("Processing item %s at stage %s", item_id, item.get("stage"))
            self.process_item(item, state, item_id)
            processed += 1

        state["last_heartbeat"] = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        state_module.save_state(state)
        self.logger.info("Pipeline run complete. Processed %d items.", processed)
        return processed

    def handle_new_idea(self, file_path):
        self.logger.info(f"Handling new idea event for file: {file_path}")
        self.run_pipeline()

    def handle_review_update(self, file_path):
        self.logger.info(f"Handling review update event for file: {file_path}")
        self.run_pipeline()

_orchestrator_instance = None

def get_orchestrator() -> "Orchestrator":
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = Orchestrator()
    return _orchestrator_instance

def get_next_actionable_items(state):
    return get_orchestrator().get_next_actionable_items(state)

def run_pipeline():
    return get_orchestrator().run_pipeline()

def transition_stage(item, new_stage, state, item_id=None):
    return get_orchestrator().transition_stage(item, new_stage, state, item_id)

def process_item(item, state, item_id):
    return get_orchestrator().process_item(item, state, item_id)

def handle_intake(item, state, item_id):
    return get_orchestrator().handle_intake(item, state, item_id)

def handle_refinement(item, state, item_id):
    return get_orchestrator().handle_refinement(item, state, item_id)

def handle_review_spec(item, state, item_id):
    return get_orchestrator().handle_review_spec(item, state, item_id)

def handle_architecture(item, state, item_id):
    return get_orchestrator().handle_architecture(item, state, item_id)

def handle_review_arch(item, state, item_id):
    return get_orchestrator().handle_review_arch(item, state, item_id)

def handle_testing(item, state, item_id):
    return get_orchestrator().handle_testing(item, state, item_id)

def handle_review_test(item, state, item_id):
    return get_orchestrator().handle_review_test(item, state, item_id)

def handle_approved(item, state, item_id):
    return get_orchestrator().handle_approved(item, state, item_id)

def handle_executing(item, state, item_id):
    return get_orchestrator().handle_executing(item, state, item_id)

def handle_done(item, state, item_id):
    return get_orchestrator().handle_done(item, state, item_id)

STAGE_HANDLERS = {
    "INTAKE": "handle_intake",
    "REFINEMENT": "handle_refinement",
    "REVIEW_SPEC": "handle_review_spec",
    "ARCHITECTURE": "handle_architecture",
    "REVIEW_ARCH": "handle_review_arch",
    "TESTING": "handle_testing",
    "REVIEW_TEST": "handle_review_test",
    "APPROVED": "handle_approved",
    "EXECUTING": "handle_executing",
    "DONE": "handle_done",
}
