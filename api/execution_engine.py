import logging
import uuid
import json
from typing import Dict, Any, Optional, Tuple
from api.workflow_state_manager import WorkflowStateManager
from api.integration_hub import IntegrationHub
from api.escalation_manager import EscalationManager
from api.managers.run_manager import RunManager

logger = logging.getLogger(__name__)

class ExecutionEngine:
    """
    The core orchestration engine that executes WorkflowTemplates as WorkflowRuns.
    Implements the Step Execution Cycle defined in engine-spec.md.
    """
    def __init__(self, state_manager: WorkflowStateManager, hub: IntegrationHub, escalator: EscalationManager):
        self.state_manager = state_manager
        self.hub = hub
        self.escalator = escalator
        self.run_manager = state_manager.runs

    def start_run(self, template_id: str, inputs: Dict[str, Any]) -> str:
        """
        Initializes and starts a new workflow run.
        """
        template = self.state_manager.templates.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        run_data = {
            "template_id": template_id,
            "status": "RUNNING",
            "current_step_index": 0,
            "inputs": inputs,
            "context": {},
            "results": {}
        }

        self.run_manager.create_run(run_id, run_data)
        self.run_manager.log_event(run_id, "RUN_STARTED", {"template_id": template_id, "inputs": inputs})
        
        # Trigger the first step asynchronously (simulated here by a direct call)
        self.process_next_step(run_id)
        
        return run_id

    def resume_run_by_item_id(self, item_id: str):
        """
        Resumes a workflow run linked to a specific Kanban item (e.g., a recovery task).
        """
        item = self.state_manager.get_item_details(item_id)
        if not item:
            logger.error(f"Resume failed: Item {item_id} not found on board")
            raise ValueError(f"Item {item_id} not found on board")
 
        # Try to find the linked run ID in the item data
        run_id = item.get("linked_run_id")
        
        # Fallback: Check the binding manager if it's not in the item data
        if not run_id:
            run_id = self.state_manager.get_run_id_for_item(item_id)
            
        if not run_id:
            logger.error(f"Resume failed: No linked_run_id found for item {item_id}. Item data: {item}")
            raise ValueError(f"No active run found for item {item_id}")
 
        logger.info(f"Resuming linked run {run_id} for item {item_id}")
        
        # Mark run as RUNNING again and trigger next step
        self.run_manager.update_run(run_id, {"status": "RUNNING"})
        self.process_next_step(run_id)
        return run_id
 
    def process_next_step(self, run_id: str):
        """
        The main loop that executes the next step in a run's lifecycle.
        """
        run = self.run_manager.get_run(run_id)
        if not run or run["status"] != "RUNNING":
            return

        template = self.state_manager.templates.get_template(run["template_id"])
        steps = template.get("steps", [])
        idx = run["current_step_index"]

        if idx >= len(steps):
            self.run_manager.update_run(run_id, {"status": "COMPLETED"})
            self.run_manager.log_event(run_id, "RUN_COMPLETED", {})
            return

        step = steps[idx]
        step_name = step.get("name", f"Step {idx}")
        
        # 1. Resolve Context
        resolved_config = self._resolve_context(step.get("config", {}), run)

        # 2. Dispatch to Adapter
        step_type = step.get("type", "HTTP")
        try:
            self.run_manager.log_event(run_id, "STEP_START", {"step": step_name, "type": step_type})
            
            # Check if this is an Orchestrator Task (HITL)
            if step_type == "ORCHESTRATOR_TASK":
                self._handle_hitl_step(run_id, step)
                return

            # Otherwise, execute via the hub
            # The hub expects execute_action(action_type, params)
            result = self.hub.execute_action(step_type, resolved_config)
            
            # 3. Record Outcome
            self.run_manager.log_event(run_id, "STEP_END", {"step": step_name, "result": result})
            
            # Update run context with result for future steps
            run_context = run.get("context", {})
            run_context[step_name] = result
            
            # Move to next step
            self.run_manager.update_run(run_id, {
                "current_step_index": idx + 1,
                "context": run_context
            })
            
            # Recurse to next step
            self.process_next_step(run_id)

        except Exception as e:
            self._handle_failure(run_id, step_name, e)

    def _resolve_context(self, config: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replaces {{variable}} placeholders in config with values from run inputs or context.
        """
        import re
        
        def replace_match(match):
            var_name = match.group(1)
            # Priority: Context (previous steps) -> Inputs (start of run)
            return str(run.get("context", {}).get(var_name, run.get("inputs", {}).get(var_name, match.group(0))))

        resolved = json.dumps(config)
        resolved = re.sub(r"\{\{(.*?)\}\}", replace_match, resolved)
        return json.loads(resolved)

    def _handle_hitl_step(self, run_id: str, step: Dict[str, Any]):
        """
        Pauses the run and escalates to the Orchestrator.
        """
        step_name = step.get("name", "HITL Step")
        target_phase = step.get("target_phase", "DISCOVERY")
        
        # Update run status to WAITING
        self.run_manager.update_run(run_id, {"status": "WAITING_FOR_HUMAN"})
        
        # Spawn the orchestrator task
        self.escalator.escalate_to_orchestrator(
            run_id=run_id,
            step_name=step_name,
            error_message=f"Manual intervention required for phase: {target_phase}"
        )
        
        self.run_manager.log_event(run_id, "RUN_PAUSED", {"reason": "HITL_STEP", "step": step_name})

    def _handle_failure(self, run_id: str, step_name: str, error: Exception):
        """
        Implements the failure classification from engine-spec.md.
        """
        error_msg = str(error)
        logger.error(f"Run {run_id} failed at step {step_name}: {error_msg}")
        
        # For this implementation, we treat all unexpected exceptions as CRITICAL
        # and escalate them to the Orchestrator.
        self.run_manager.update_run(run_id, {"status": "BLOCKED"})
        
        self.escalator.escalate_to_orchestrator(
            run_id=run_id,
            step_name=step_name,
            error_message=error_msg
        )
        
        self.run_manager.log_event(run_id, "RUN_BLOCKED", {"error": error_msg})
