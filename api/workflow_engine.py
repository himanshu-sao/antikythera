import os
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from api.workflow_state_manager import WorkflowStateManager
from api.adapters.internal import InternalKanbanAdapter
from api.adapters.github import GitHubAdapter
from api.adapters.jira import JiraAdapter

class WorkflowEngine:
    def __init__(self, state_dir: str):
        self.state_mgr = WorkflowStateManager(state_dir)
        # Registry of available adapters
        self.adapters = {
            "INTERNAL": InternalKanbanAdapter(),
            "GITHUB": GitHubAdapter(),
            "JIRA": JiraAdapter()
        }

    def trigger_run(self, template_id: str, inputs: Dict[str, Any], trigger_event_id: Optional[str] = None) -> Optional[str]:
        """Creates a run from a template and starts execution."""
        template = self.state_mgr.get_template(template_id)
        if not template:
            return None
        
        # 1. Idempotency check (deduplication)
        if trigger_event_id:
            # In a real system, we'd check the database for this key
            # For this Wave, we'll assume triggers are unique or handled by the caller
            pass
            
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        run_data = {
            "template_id": template_id,
            "template_version": template.get("version", "1.0.0"),
            "status": "ACTIVE",
            "current_step_id": template["steps"][0]["step_id"],
            "inputs": inputs,
            "started_at": datetime.utcnow().isoformat() + "Z"
        }
        
        if self.state_mgr.create_run(run_id, run_data):
            self.state_mgr.log_event(run_id, "RUN_STARTED", {"template_id": template_id}, actor="system")
            # Start execution in a separate "process" (for now, we'll simulate it)
            self.execute_run(run_id)
            return run_id
        return None

    def execute_run(self, run_id: str):
        """The core execution loop. Processes steps until a pause or completion."""
        run = self.state_mgr.get_run(run_id)
        if not run or run["status"] not in ["ACTIVE", "BLOCKED"]:
            return

        template = self.state_mgr.get_template(run["template_id"])
        if not template:
            return

        while True:
            current_step_id = run.get("current_step_id")
            step = next((s for s in template["steps"] if s["step_id"] == current_step_id), None)
            
            if not step:
                self.state_mgr.update_run(run_id, {"status": "FAILED"})
                self.state_mgr.log_event(run_id, "ERROR", {"message": "Step not found"}, actor="system")
                break

            # 1. Log Step Start
            self.state_mgr.log_event(run_id, "STEP_START", {"step_id": current_step_id}, actor="system")

            # 2. Dispatch to Adapter
            category = step.get("category")
            # Determine adapter type from step config or default to INTERNAL
            adapter_type = step.get("config", {}).get("adapter", "INTERNAL") 
            adapter = self.adapters.get(adapter_type)
            
            if not adapter:
                self.state_mgr.update_run(run_id, {"status": "FAILED"})
                self.state_mgr.log_event(run_id, "ERROR", {"message": f"No adapter for {adapter_type}"}, actor="system")
                break

            # Resolve config (simple replacement of {{inputs}})
            config = step.get("config", {})
            # (Simple variable resolution logic would go here)

            try:
                result = adapter.execute(run_id, config, run["inputs"])
                if result.get("status") == "success":
                    # 3. Log Step End
                    self.state_mgr.log_event(run_id, "STEP_END", {"step_id": current_step_id, "result": result}, actor="system")
                    
                    # 4. Handle Board Mapping (if any)
                    if "board_mapping" in step:
                        # Move the card on the board
                        self.state_mgr.bind_run_to_item(run_id, "AUTO-GEN") # Simulating auto-gen
                        # In real logic, we'd actually create the item and use that ID
                        pass
                    
                    # 5. Transition to next step
                    next_step = step.get("next_step")
                    if next_step:
                        self.state_mgr.update_run(run_id, {"current_step_id": next_step})
                        run["current_step_id"] = next_step # Update local copy for loop
                    else:
                        self.state_mgr.update_run(run_id, {"status": "COMPLETED"})
                        self.state_mgr.log_event(run_id, "RUN_COMPLETED", {}, actor="system")
                        break
                else:
                    # Handle Failure
                    self.state_mgr.update_run(run_id, {"status": "BLOCKED"})
                    self.state_mgr.log_event(run_id, "ERROR", {"step_id": current_step_id, "error": result.get("message")}, actor="system")
                    break
            except Exception as e:
                self.state_mgr.update_run(run_id, {"status": "FAILED"})
                self.state_mgr.log_event(run_id, "ERROR", {"message": str(e)}, actor="system")
                break
