import logging
from typing import Dict, Any, Optional
from api.workflow_state_manager import WorkflowStateManager

logger = logging.getLogger(__name__)

class EscalationManager:
    """
    Handles the transition of failed automation runs into 
    Human-in-the-Loop (HITL) Orchestrator tasks.
    """
    def __init__(self, state_manager: WorkflowStateManager):
        self.state_manager = state_manager

    def escalate_to_orchestrator(self, run_id: str, step_name: str, error_message: str) -> Optional[str]:
        """
        Spawns a recovery task on the Kanban board for a failed run.
        Returns the new item_id if successful.
        """
        item_id = f"REC-{run_id[-6:]}" # Create a short, unique recovery ID
        title = f"Recovery: {step_name}"
        goal = f"Resolve failure: {error_message}"
        description = (
            f"This task was automatically spawned because a WorkflowRun failed.\n\n"
            f"Run ID: {run_id}\n"
            f"Failed Step: {step_name}\n"
            f"Error: {error_message}\n\n"
            f"The automation is now PAUSED. Once this task is marked DONE, the run will resume."
        )

        logger.info(f"Escalating run {run_id} to orchestrator task {item_id}")

        # 1. Create the item on the Kanban board
        success = self.state_manager.create_item(
            item_id=item_id,
            title=title,
            goal=goal,
            description=description
        )

        if not success:
            logger.error(f"Failed to create escalation item {item_id}")
            return None

        # 2. Store the link to the original WorkflowRun for resumption
        self.state_manager.update_item(item_id, {
            "current_phase": "DISCOVERY",
            "linked_run_id": run_id
        })

        # 3. Add a system comment for traceability
        self.state_manager.add_comment(
            item_id=item_id,
            author="System-Escalator",
            body=f"Linked to WorkflowRun {run_id}. Automation paused."
        )

        return item_id
