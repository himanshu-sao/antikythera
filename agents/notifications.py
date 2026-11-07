import logging
from agents import logger as task_logger

logger = logging.getLogger(__name__)


def notify_stage_transition(item_id, item, old_stage, new_stage, agent):
    """
    Records a stage change: one INFO line on the module logger plus the
    per-task timeline entry. No external notification is sent.
    """
    logger.info(
        "Stage transition for %s: %s -> %s (agent: %s)",
        item_id, old_stage, new_stage, agent or "orchestrator",
    )

    # Task logging integration (per-item timeline.jsonl)
    try:
        t_logger = task_logger.get_logger(item_id)
        t_logger.info(agent or "orchestrator", "STAGE_TRANSITION", f"Moved from {old_stage} to {new_stage}")
    except Exception as e:
        logger.error("Failed to log stage transition for %s: %s", item_id, str(e))
