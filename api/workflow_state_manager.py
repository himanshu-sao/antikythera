from typing import Dict, Any, Optional, List
from api.managers.template_manager import TemplateManager
from api.managers.run_manager import RunManager
from api.managers.binding_manager import BindingManager
from api.managers.kanban_state_manager import KanbanStateManager

class WorkflowStateManager:
    """
    Facade class that coordinates different state managers.
    Maintains backward compatibility with existing imports.
    """
    def __init__(self, base_dir: str):
        self.templates = TemplateManager(base_dir)
        self.runs = RunManager(base_dir)
        self.bindings = BindingManager(base_dir)
        self.kanban = KanbanStateManager(base_dir)

    # --- Kanban / Item Management (Delegated to KanbanStateManager) ---
    def load_state(self) -> Dict[str, Any]:
        return self.kanban.load_state()

    def create_item(self, item_id: str, title: str, source_type: Optional[str] = None, source_value: Optional[str] = None, due_date: Optional[str] = None) -> bool:
        return self.kanban.create_item(item_id, title, source_type, source_value, due_date)

    def update_item(self, item_id: str, updates: Dict[str, Any]) -> bool:
        return self.kanban.update_item(item_id, updates)

    def delete_item(self, item_id: str) -> bool:
        return self.kanban.delete_item(item_id)

    def get_item_details(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.kanban.get_item_details(item_id)

    def add_comment(self, item_id: str, author: str, body: str) -> Optional[Dict[str, Any]]:
        return self.kanban.add_comment(item_id, author, body)

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
        return self.runs.update_run(run_id, updates)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.runs.get_run(run_id)

    def log_event(self, run_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system") -> bool:
        return self.runs.log_event(run_id, event_type, payload, actor)

    def get_run_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        return self.runs.get_run_timeline(run_id)

    # --- Binding Management (Delegated to BindingManager) ---
    def bind_run_to_item(self, run_id: str, item_id: str, binding_type: str = "PRIMARY") -> bool:
        return self.bindings.bind_run_to_item(run_id, item_id, binding_type)

    def get_bindings_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        return self.bindings.get_bindings_for_run(run_id)

    def get_run_id_for_item(self, item_id: str) -> Optional[str]:
        return self.bindings.get_run_id_for_item(item_id)
