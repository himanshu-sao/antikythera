import time
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from api.workflow_engine import WorkflowEngine
from api.workflow_state_manager import WorkflowStateManager

class WorkflowTriggerManager:
    """
    Manages the ingestion of events from external sources and 
    maps them to workflow runs.
    """
    def __init__(self, engine: WorkflowEngine, state_mgr: WorkflowStateManager):
        self.engine = engine
        self.state_mgr = state_mgr

    def handle_webhook(self, template_id: str, payload: Dict[str, Any]) -> Optional[str]:
        """Handles an incoming webhook and triggers the associated workflow."""
        template = self.state_mgr.get_template(template_id)
        if not template:
            return None
        
        # Validate trigger config (simple match)
        trigger_cfg = template.get("trigger", {})
        if trigger_cfg.get("type") != "WEBHOOK":
            return None
        
        # Use a part of the payload as the deduplication key
        event_id = payload.get("event_id", uuid.uuid4().hex)
        
        # Trigger the run
        return self.engine.trigger_run(template_id, payload, trigger_event_id=event_id)

    def poll_external_sources(self):
        """
        Simulates a polling loop that checks external sources 
        (like Jira JQL) and triggers runs for new items.
        """
        # In a real system, this would be a background thread/task
        templates = self.state_mgr.list_templates()
        for template in templates:
            trigger = template.get("trigger", {})
            if trigger.get("type") == "POLLING":
                # Simulate finding a new item
                print(f"Polling for {template['template_id']}...")
                # Mock: find one item every time we poll for testing
                self.engine.trigger_run(
                    template["template_id"], 
                    {"item_id": f"POLL-{uuid.uuid4().hex[:4]}", "source": "Jira"},
                    trigger_event_id=f"poll_{int(time.time())}"
                )
