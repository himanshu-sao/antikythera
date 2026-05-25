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

    def promote_to_pattern(self, item_id: str, artifact_name: str, content: str) -> bool:
        """
        Promotes a successful artifact into the central knowledge base (brain/patterns.md).
        """
        try:
            pattern_path = "brain/patterns.md"
            os.makedirs(os.path.dirname(pattern_path), exist_ok=True)
            
            entry = f"\n\n## Pattern: {item_id} - {artifact_name}\n"
            entry += f"**Promoted at:** {datetime.utcnow().isoformat()}Z\n\n"
            entry += f"{content}\n\n---\n"
            
            with open(pattern_path, "a") as f:
                f.write(entry)
            return True
        except Exception as e:
            print(f"Pattern promotion failed: {e}")
            return False

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
                        # In a real system, we'd find the item_id from the run binding
                        # For this implementation, we assume the 'item_id' is provided in the config
                        item_id = step.get("config", {}).get("item_id")
                        if item_id:
                            self.state_mgr.bind_run_to_item(run_id, item_id)
                        else:
                            # Simulate auto-generation if not provided
                            self.state_mgr.bind_run_to_item(run_id, "AUTO-GEN")
                        
                        # ACTUALLY MOVE THE ITEM ON THE BOARD
                        if item_id:
                            from api.state_manager import StateManager
                            main_state_mgr = StateManager("./automation-ideas/pipeline-state.json")
                            main_state_mgr.update_item(item_id, {"stage": step["board_mapping"]["stage"]})

                    
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
