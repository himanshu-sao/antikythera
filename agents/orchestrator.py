import copy
import datetime
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

# 2.4 / T18: the API stores lowercase priorities (api/constants.py
# VALID_PRIORITIES). Ranks are matched case-insensitively; lower rank runs first.
PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_UNKNOWN_PRIORITY_RANK = 4

_MISSING = object()


def _changed_keys(before, after):
    """Top-level keys that were added, changed or removed between two item dicts."""
    return {
        key
        for key in set(before) | set(after)
        if before.get(key, _MISSING) != after.get(key, _MISSING)
    }


def _priority_rank(priority):
    """Sort rank for a stored priority. Missing/None -> medium; unknown -> last."""
    if not isinstance(priority, str) or not priority.strip():
        return PRIORITY_RANK["medium"]
    return PRIORITY_RANK.get(priority.strip().lower(), _UNKNOWN_PRIORITY_RANK)

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
        
        actionable.sort(key=lambda x: _priority_rank(x[1].get("priority")))
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
        """Process every actionable item once, then record a heartbeat.

        Merge rule (2.11 / T1, decision D10). API edits can land on disk while
        a run is in flight, so the pipeline never writes back a whole-state
        snapshot taken at the start of the run:

        1. Each item is processed against the snapshot loaded at the start of
           the run. Before the handler runs, a deep copy ``before`` is taken.
        2. The keys whose values differ between ``before`` and the processed
           item (added, changed, or removed) are that item's *pipeline-owned*
           changes. Everything else is not ours to write.
        3. Under the state lock, the latest state is re-read from disk and only
           those keys are applied onto the freshly read item. Keys the handler
           did not change (e.g. a title edited by the API) keep their current
           values. Values are replaced wholesale, so a list the handler
           changed (``history``) is written as the handler left it.
        4. If the item was deleted meanwhile, nothing is written, so it is not
           resurrected.
        5. The fresh state is saved.

        Returns the number of items whose handler completed without raising.
        """
        self.logger.info("Pipeline run starting")
        state = state_module.load_state()
        actionable = self.get_next_actionable_items(state)

        processed = 0
        for item_id, item in actionable:
            self.logger.info("Processing item %s at stage %s", item_id, item.get("stage"))
            before = copy.deepcopy(item)
            self.process_item(item, state, item_id)
            processed += 1
            self._commit_item(item_id, before, item)

        self._commit_heartbeat()
        self.logger.info("Pipeline run complete. Processed %d items.", processed)
        return processed

    def _commit_item(self, item_id, before, after):
        """Merge one item's pipeline-owned changes into the latest on-disk state.

        Returns True if something was written. See ``run_pipeline`` for the rule.
        """
        changed = _changed_keys(before, after)
        if not changed:
            return False
        with state_module.state_lock():
            fresh = state_module.load_state()
            current = fresh.get("items", {}).get(item_id)
            if current is None:
                self.logger.info("Item %s was deleted during the run; not resurrecting it", item_id)
                return False
            for key in changed:
                if key in after:
                    current[key] = copy.deepcopy(after[key])
                else:
                    current.pop(key, None)
            state_module.save_state(fresh)
        return True

    def _commit_heartbeat(self):
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        with state_module.state_lock():
            fresh = state_module.load_state()
            fresh["last_heartbeat"] = now
            state_module.save_state(fresh)

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
