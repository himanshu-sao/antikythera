import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable
from api.workflow_state_manager import WorkflowStateManager

class RetryManager:
    """
    Implements the Antikythera failure handling standard:
    3 retries at 5, 10, and 15-minute intervals before blocking.
    """
    RETRY_INTERVALS = [5, 10, 15] # in minutes

    def __init__(self, state_manager: WorkflowStateManager):
        self.state_manager = state_manager

    def should_retry(self, run_id: str) -> Optional[int]:
        """
        Determines if a run should be retried and returns the next interval.
        Returns None if the run should be moved to BLOCKED.
        """
        run = self.state_manager.get_run(run_id)
        if not run:
            return None

        retry_count = run.get("retry_count", 0)
        
        if retry_count < len(self.RETRY_INTERVALS):
            return self.RETRY_INTERVALS[retry_count]
        
        return None

    def record_failure(self, run_id: str, error_msg: str):
        """Records a failure and increments the retry counter."""
        run = self.state_manager.get_run(run_id)
        if not run:
            return

        retry_count = run.get("retry_count", 0) + 1
        
        # Log the failure event
        self.state_manager.log_event(
            run_id, 
            "FAILURE", 
            {"error": error_msg, "retry_count": retry_count}, 
            actor="system"
        )

        updates = {"retry_count": retry_count}
        
        # If we've exhausted retries, move to BLOCKED
        if retry_count > len(self.RETRY_INTERVALS):
            updates["status"] = "BLOCKED"
            self.state_manager.log_event(
                run_id, 
                "STATE_TRANSITION", 
                {"from": run.get("status"), "to": "BLOCKED", "reason": "Exhausted retries"}, 
                actor="system"
            )

        self.state_manager.update_run(run_id, updates)
