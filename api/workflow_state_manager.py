from typing import Dict, Any, Optional, List
import os
from api.managers.template_manager import TemplateManager
from api.managers.run_manager import RunManager
from api.managers.binding_manager import BindingManager
from api.managers.kanban_state_manager import KanbanStateManager
from api.brain_managers import BrainManager, ObserverManager
from api.brain_schemas import ObserverEvent

class WorkflowStateManager:
    """
    Facade class that coordinates different state managers.
    Maintains backward compatibility with existing imports.
    """
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.templates = TemplateManager(base_dir)
        self.runs = RunManager(base_dir)
        self.bindings = BindingManager(base_dir)
        self.kanban = KanbanStateManager(base_dir)
        
        # Intelligence Layer
        knowledge_dir = os.path.join(base_dir, "knowledge")
        deltas_dir = os.path.join(knowledge_dir, "deltas")
        self.brain = BrainManager(knowledge_dir, deltas_dir)
        # Ensure the knowledge directory exists for file operations
        os.makedirs(self.brain.knowledge_dir, exist_ok=True)
        self.observer = ObserverManager(self.brain, self.runs)

    # --- Intelligence Integration ---
    def notify_observer(self, event_type: str, event_data: Dict[str, Any], actor: str = "system"):
        """Triggers the background observer to process an event."""
        event = ObserverEvent(
            event_type=event_type,
            event_data=event_data,
            actor=actor
        )
        self.observer.process_event(event)

    # --- Kanban / Item Management (Delegated to KanbanStateManager) ---
    def load_state(self) -> Dict[str, Any]:
        return self.kanban.load_state()

    def create_item(self, item_id: str, title: str, goal: Optional[str] = None, description: Optional[str] = None, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None, complexity: Optional[str] = None) -> bool:
        success = self.kanban.create_item(item_id, title, goal, description, source_type, source_value, due_date, complexity)
        if success:
            self.notify_observer("KANBAN_TRANSITION", {"item_id": item_id, "body": f"Created item: {title}"})
        return success

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        success = self.kanban.update_item(item_id, updates)
        if success:
            # If the update is a stage change, notify observer
            if "stage" in updates:
                new_stage = updates["stage"]
                self.notify_observer("KANBAN_TRANSITION", {"item_id": item_id, "body": f"Moved to stage: {new_stage}"})
                
                # Automated Learning: If moved to DONE, scan logs for patterns
                if new_stage == "DONE":
                    # Find associated run
                    run_id = self.get_run_id_for_item(item_id)
                    if run_id:
                        patterns = self.observer.analyze_kanban_logs(run_id)
                        for pattern in patterns:
                            # Directly notify observer of the pattern (simulated)
                            self.notify_observer("TASK_SUCCESS", {
                                "workflow_summary": f"Completed pattern for {item_id}: {pattern.reason}"
                            })
        return success

    def delete_item(self, item_id: str) -> bool:
        return self.kanban.delete_item(item_id)

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.kanban.get_item_details(item_id)

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        comment = self.kanban.add_comment(item_id, author, body)
        if comment:
            # Notify observer about the new comment
            self.notify_observer("USER_INTERVENTION", {"user_comment": body, "item_id": item_id})
        return comment

    def delete_comment(self, item_id: str, comment_id: str) -> bool:
        return self.kanban.delete_comment(item_id, comment_id)

    def reorder_items(self, stage: str, ordered_ids: List[str]):
        self.kanban.reorder_items(stage, ordered_ids)

    # --- Template Management (Delegated to TemplateManager) ---
    def save_template(self, template_id: str, template_data: Dict[str, Any]) -> bool:
        return self.templates.save_template(template_id, template_data)

    def delete_template(self, template_id: str) -> bool:
        return self.templates.delete_template(template_id)

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        return self.templates.get_template(template_id)

    def list_templates(self) -> List[Dict[str, Any]]:
        return self.templates.list_templates()

    # --- Run Management (Delegated to RunManager) ---
    def create_run(self, run_id: str, run_data: Dict[str, Any]) -> bool:
        return self.runs.create_run(run_id, run_data)

    def update_run(self, run_id: str, updates: Dict[str, Any]) -> bool:
        success = self.runs.update_run(run_id, updates)
        if success:
            # Check for task completion in the update
            if updates.get("status") == "COMPLETED":
                self.notify_observer("TASK_SUCCESS", {"workflow_summary": updates.get("summary", "Task completed successfully.")})
        return success

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.runs.get_run(run_id)

    def log_event(self, run_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system") -> bool:
        success = self.runs.log_event(run_id, event_type, payload, actor)
        if success:
            # Automatically notify observer of every logged event
            self.notify_observer(event_type, payload, actor)
        return success

    def get_run_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        return self.runs.get_run_timeline(run_id)

    # --- Binding Management (Delegated to BindingManager) ---
    def bind_run_to_item(self, run_id: str, item_id: str, binding_type: str = "PRIMARY") -> bool:
        return self.bindings.bind_run_to_item(run_id, item_id, binding_type)

    def get_bindings_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        return self.bindings.get_bindings_for_run(run_id)

    def get_run_id_for_item(self, item_id: str) -> Optional[str]:
        return self.bindings.get_run_id_for_item(item_id)
