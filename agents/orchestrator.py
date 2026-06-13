import logging
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from agents import state as state_module
from agents.constants import STAGE_AGENTS, STAGE_HANDLERS
from agents.notifications import notify_stage_transition
from agents.handlers import StageHandler
# Expose sub‑modules for test patches
import agents.refiner as refiner
import agents.architect as architect
import agents.tester as tester
# Ensure an event loop exists for async‑compatible tests
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.handlers = StageHandler(self)

    def get_next_actionable_items(self, state):
        items = state.get("items", {})
        actionable = []
        for item_id, item in items.items():
            stage = item.get("stage", "INTAKE")
            # Check if item is blocked by a review stage
            from agents.constants import REVIEW_STAGES
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
        item["assigned_agent"] = agent

        if item_id:
            # Log history only if the item exists in the state; otherwise skip to avoid KeyError.
            if item_id.upper() in state.get("items", {}):
                state_module.add_history_entry(state, item_id, new_stage, agent=agent)
            else:
                logger.warning("History entry skipped for unknown item ID %s", item_id)
            notify_stage_transition(item_id, item, old_stage, new_stage, agent)

        self.logger.info("Transitioned %s: %s -> %s (agent: %s)", item_id or "?", old_stage, new_stage, agent or "none")

    def process_item(self, item, state, item_id):
        stage = item.get("stage", "INTAKE")
        handler_name = STAGE_HANDLERS.get(stage)
        if handler_name:
            method = getattr(self.handlers, handler_name)
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

        import datetime
        state["last_heartbeat"] = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        state_module.save_state(state)
        self.logger.info("Pipeline run complete. Processed %d items.", processed)
        return processed

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

# Facade functions for backward compatibility
def get_next_actionable_items(state):
    return get_orchestrator().get_next_actionable_items(state)

def run_pipeline():
    return get_orchestrator().run_pipeline()

def transition_stage(item, new_stage, state, item_id=None):
    return get_orchestrator().transition_stage(item, new_stage, state, item_id)

def process_item(item, state, item_id):
    return get_orchestrator().process_item(item, state, item_id)

def handle_intake(item, state, item_id):
    return get_orchestrator().handlers.handle_intake(item, state, item_id)

def handle_refinement(item, state, item_id):
    return get_orchestrator().handlers.handle_refinement(item, state, item_id)

def handle_review_spec(item, state, item_id):
    return get_orchestrator().handlers.handle_review_spec(item, state, item_id)

def handle_architecture(item, state, item_id):
    return get_orchestrator().handlers.handle_architecture(item, state, item_id)

def handle_review_arch(item, state, item_id):
    return get_orchestrator().handlers.handle_review_arch(item, state, item_id)

def handle_testing(item, state, item_id):
    return get_orchestrator().handlers.handle_testing(item, state, item_id)

def handle_review_test(item, state, item_id):
    return get_orchestrator().handlers.handle_review_test(item, state, item_id)

def handle_approved(item, state, item_id):
    return get_orchestrator().handlers.handle_approved(item, state, item_id)

def handle_executing(item, state, item_id):
    return get_orchestrator().handlers.handle_executing(item, state, item_id)

def handle_done(item, state, item_id):
    return get_orchestrator().handlers.handle_done(item, state, item_id)
