import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from apscheduler.schedulers.background import BackgroundScheduler as APScheduler
from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub

class AntikytheraScheduler:
    """
    The Clock of Antikythera.
    Handles periodic polling and timed executions.
    """
    def __init__(self, base_dir: str, state_manager: WorkflowStateManager, hub: IntegrationHub):
        self.base_dir = base_dir
        self.state_manager = state_manager
        self.hub = hub
        self.scheduler = APScheduler()
        self._job_map = {} # job_id -> template_id

    def start(self):
        self.scheduler.start()
        logging.info("Antikythera Scheduler started.")

    def stop(self):
        self.scheduler.shutdown()

    def schedule_polling(self, template_id: str, interval_minutes: int, poll_func: Callable):
        """Schedules a polling task for a specific template."""
        job_id = f"poll_{template_id}"
        
        # Remove existing job if it exists
        try:
            self.scheduler.remove_job(job_id)
        except:
            pass

        self.scheduler.add_job(
            poll_func, 
            'interval', 
            minutes=interval_minutes, 
            id=job_id,
            args=[template_id]
        )
        self._job_map[job_id] = template_id
        return job_id

    def cancel_polling(self, template_id: str):
        job_id = f"poll_{template_id}"
        try:
            self.scheduler.remove_job(job_id)
        except:
            pass
            
    def get_active_jobs(self) -> List[str]:
        return [job.id for job in self.scheduler.get_jobs()]
