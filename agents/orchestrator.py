"""
Orchestrator Agent — main loop, state machine, and agent dispatch.

The Orchestrator is the central controller of the Hermes pipeline.
It reads pipeline state, dispatches items to the appropriate agents
based on their current stage, and updates state after each action.
"""

import logging

from agents import state as state_module
from agents import refiner
from agents import architect
from agents import tester
from agents import audit as audit_module

logger = logging.getLogger(__name__)

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


def get_next_actionable_items(state):
    """
    Get items that are ready for processing (not blocked on review).

    An item is actionable if:
    - Its stage is NOT a review stage, OR
    - Its stage IS a review stage but review_status is "APPROVED"

    Args:
        state (dict): The pipeline state.

    Returns:
        list: List of (item_id, item) tuples for actionable items.
    """
    items = state.get("items", {})
    actionable = []
    for item_id, item in items.items():
        stage = item.get("stage", "INTAKE")
        if stage in REVIEW_STAGES:
            review_status = item.get("review_status", "PENDING")
            if review_status != "APPROVED":
                continue
        actionable.append((item_id, item))
    # Sort by priority: High first, then Medium, then Low
    priority_order = {"High": 0, "Medium": 1, "Low": 2}
    actionable.sort(key=lambda x: priority_order.get(x[1].get("priority", "Medium"), 99))
    return actionable


def transition_stage(item, new_stage, state, item_id=None):
    """
    Transition an item to a new stage.

    Updates the item's stage, adds a history entry, and sets the
    assigned agent for the new stage.

    Args:
        item (dict): The pipeline item.
        new_stage (str): The target stage.
        state (dict): The pipeline state.
        item_id (str, optional): The item ID (used for history).
    """
    old_stage = item.get("stage", "INTAKE")
    item["stage"] = new_stage
    agent = STAGE_AGENTS.get(new_stage)
    if agent:
        item["assigned_agent"] = agent
    else:
        item["assigned_agent"] = None

    if item_id:
        state_module.add_history_entry(state, item_id, new_stage, agent=agent)

    logger.info("Transitioned %s: %s -> %s (agent: %s)", item_id or "?", old_stage, new_stage, agent or "none")


# --- Stage Handlers ---

def handle_intake(item, state, item_id):
    """Handle INTAKE stage: transition to REFINEMENT."""
    logger.info("Processing %s at INTAKE stage", item_id)
    transition_stage(item, "REFINEMENT", state, item_id)


def handle_refinement(item, state, item_id):
    """Handle REFINEMENT stage: run Refiner Agent, transition to REVIEW_SPEC."""
    logger.info("Processing %s at REFINEMENT stage", item_id)
    title = item.get("title", "Untitled")
    try:
        confidence = refiner.refine_idea(item_id, title)
        item["confidence_score"] = confidence
        logger.info("Refiner completed for %s with confidence %d", item_id, confidence)
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
        item["blocked_reason"] = f"Refiner failed: {str(e)}"
    transition_stage(item, "REVIEW_SPEC", state, item_id)


def handle_review_spec(item, state, item_id):
    """Handle REVIEW_SPEC stage: check review_status."""
    logger.info("Processing %s at REVIEW_SPEC stage", item_id)
    review_status = item.get("review_status", "PENDING")
    if review_status == "APPROVED":
        logger.info("%s review approved, transitioning to ARCHITECTURE", item_id)
        transition_stage(item, "ARCHITECTURE", state, item_id)
    elif review_status == "NEEDS_REVISION":
        logger.info("%s needs revision, transitioning back to REFINEMENT", item_id)
        transition_stage(item, "REFINEMENT", state, item_id)
    else:
        logger.info("%s review pending, waiting for owner", item_id)


def handle_architecture(item, state, item_id):
    """Handle ARCHITECTURE stage: run Architect Agent, transition to REVIEW_ARCH."""
    logger.info("Processing %s at ARCHITECTURE stage", item_id)
    try:
        confidence = architect.architect_idea(item_id)
        item["confidence_score"] = confidence
        logger.info("Architect completed for %s with confidence %d", item_id, confidence)
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
        item["blocked_reason"] = f"Architect failed: {str(e)}"
    transition_stage(item, "REVIEW_ARCH", state, item_id)


def handle_review_arch(item, state, item_id):
    """Handle REVIEW_ARCH stage: check review_status."""
    logger.info("Processing %s at REVIEW_ARCH stage", item_id)
    review_status = item.get("review_status", "PENDING")
    if review_status == "APPROVED":
        logger.info("%s architecture review approved, transitioning to TESTING", item_id)
        transition_stage(item, "TESTING", state, item_id)
    elif review_status == "NEEDS_REVISION":
        logger.info("%s architecture needs revision, transitioning back to ARCHITECTURE", item_id)
        transition_stage(item, "ARCHITECTURE", state, item_id)
    else:
        logger.info("%s architecture review pending, waiting for owner", item_id)


def handle_testing(item, state, item_id):
    """Handle TESTING stage: run Tester Agent, transition to REVIEW_TEST."""
    logger.info("Processing %s at TESTING stage", item_id)
    try:
        confidence = tester.tester_idea(item_id, use_docker=False)
        item["confidence_score"] = confidence
        logger.info("Tester completed for %s with confidence %d", item_id, confidence)
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
        item["blocked_reason"] = f"Tester failed: {str(e)}"
    transition_stage(item, "REVIEW_TEST", state, item_id)


def handle_review_test(item, state, item_id):
    """Handle REVIEW_TEST stage: check review_status."""
    logger.info("Processing %s at REVIEW_TEST stage", item_id)
    review_status = item.get("review_status", "PENDING")
    if review_status == "APPROVED":
        logger.info("%s test review approved, transitioning to APPROVED", item_id)
        transition_stage(item, "APPROVED", state, item_id)
    elif review_status == "NEEDS_REVISION":
        logger.info("%s tests need revision, transitioning back to TESTING", item_id)
        transition_stage(item, "TESTING", state, item_id)
    else:
        logger.info("%s test review pending, waiting for owner", item_id)


def handle_approved(item, state, item_id):
    """Handle APPROVED stage: transition to EXECUTING."""
    logger.info("Processing %s at APPROVED stage", item_id)
    transition_stage(item, "EXECUTING", state, item_id)


def handle_executing(item, state, item_id):
    """Handle EXECUTING stage: transition to DONE."""
    logger.info("Processing %s at EXECUTING stage", item_id)
    transition_stage(item, "DONE", state, item_id)


def handle_done(item, state, item_id):
    """Handle DONE stage: no-op."""
    logger.info("%s is already DONE, skipping", item_id)


# Stage handler dispatch table
STAGE_HANDLERS = {
    "INTAKE": handle_intake,
    "REFINEMENT": handle_refinement,
    "REVIEW_SPEC": handle_review_spec,
    "ARCHITECTURE": handle_architecture,
    "REVIEW_ARCH": handle_review_arch,
    "TESTING": handle_testing,
    "REVIEW_TEST": handle_review_test,
    "APPROVED": handle_approved,
    "EXECUTING": handle_executing,
    "DONE": handle_done,
}


def process_item(item, state, item_id):
    """
    Dispatch a single pipeline item to the correct stage handler.

    Args:
        item (dict): The pipeline item.
        state (dict): The pipeline state.
        item_id (str): The item ID.
    """
    stage = item.get("stage", "INTAKE")
    handler = STAGE_HANDLERS.get(stage)
    if handler:
        handler(item, state, item_id)
    else:
        logger.warning("No handler for stage %s on item %s", stage, item_id)


def run_pipeline():
    """
    Main entry point for the pipeline.

    Loads state, finds actionable items, processes each one,
    and saves the updated state.

    Returns:
        int: Number of items processed.
    """
    logger.info("Pipeline run starting")
    state = state_module.load_state()
    actionable = get_next_actionable_items(state)

    processed = 0
    for item_id, item in actionable:
        logger.info("Processing item %s at stage %s", item_id, item.get("stage"))
        process_item(item, state, item_id)
        processed += 1

    state["last_heartbeat"] = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    state_module.save_state(state)
    logger.info("Pipeline run complete. Processed %d items.", processed)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_pipeline()