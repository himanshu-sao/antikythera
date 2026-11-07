from datetime import datetime
from typing import Optional
from api.settings_store import get_setting
from api.workflow_state_manager import WorkflowStateManager

class RetryManager:
    """
    Implements the Antikythera failure handling standard: retries at the
    ``retry_delays_min`` setting (default 5, 10, 15 minutes), then BLOCKED.

    The delays are read per call (``get_setting``), so a Settings change takes
    effect on the next failure without a restart.
    """

    def __init__(self, state_manager: WorkflowStateManager):
        self.state_manager = state_manager

    @staticmethod
    def retry_intervals() -> list:
        """Current retry delays in minutes (the ``retry_delays_min`` setting)."""
        return list(get_setting("retry_delays_min"))

    def should_retry(self, run_id: str) -> Optional[int]:
        """
        Determines if a run should be retried and returns the next interval.
        Returns None if the run should be moved to BLOCKED.
        """
        run = self.state_manager.get_run(run_id)
        if not run:
            return None

        retry_count = run.get("retry_count", 0)
        intervals = self.retry_intervals()

        if retry_count < len(intervals):
            return intervals[retry_count]
        
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
        if retry_count > len(self.retry_intervals()):
            updates["status"] = "BLOCKED"
            self.state_manager.log_event(
                run_id, 
                "STATE_TRANSITION", 
                {"from": run.get("status"), "to": "BLOCKED", "reason": "Exhausted retries"}, 
                actor="system"
            )

        self.state_manager.update_run(run_id, updates)
