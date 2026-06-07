import logging
import yaml
import os
from agents import telegram
from agents import logger as task_logger

logger = logging.getLogger(__name__)

def notify_stage_transition(item_id, item, old_stage, new_stage, agent):
    """
    Handles the external notifications (Telegram, Task Logs) when an item changes stage.
    """
    # 1. Task Logging Integration
    try:
        t_logger = task_logger.get_logger(item_id)
        t_logger.info(agent or "orchestrator", "STAGE_TRANSITION", f"Moved from {old_stage} to {new_stage}")
    except Exception as e:
        logger.error("Failed to log stage transition for %s: %s", item_id, str(e))

    # 2. Telegram Notification
    try:
        # In a real production app, config would be loaded once at startup
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        tg = telegram.TelegramHandler(config)
        
        # Only notify on Review stages or completion
        from agents.constants import REVIEW_STAGES
        if new_stage in REVIEW_STAGES or new_stage == "DONE":
            tg.send_notification(
                item_id=item_id,
                stage=new_stage,
                title=item.get("title", "Untitled"),
                confidence=item.get("confidence_score")
            )
    except Exception as e:
        logger.error("Failed to send Telegram notification for %s: %s", item_id, str(e))
