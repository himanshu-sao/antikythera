from datetime import datetime
from typing import Dict, Any, Optional, List
from api.managers.base import BaseJSONManager

class TemplateManager(BaseJSONManager):
    def __init__(self, base_dir: str):
        super().__init__(base_dir, "workflow_templates.json")

    def save_template(self, template_id: str, template_data: Dict[str, Any]) -> bool:
        try:
            templates = self._load()
            template_data["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if "created_at" not in template_data:
                template_data["created_at"] = datetime.utcnow().isoformat() + "Z"
            
            templates[template_id] = template_data
            self._save(templates)
            return True
        except Exception:
            return False

    def delete_template(self, template_id: str) -> bool:
        try:
            templates = self._load()
            if template_id not in templates:
                return False
            del templates[template_id]
            self._save(templates)
            return True
        except Exception:
            return False

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        templates = self._load()
        template = templates.get(template_id)
        if template:
            # Ensure frontend-required fields exist
            if "name" not in template:
                template["name"] = template_id
            if "trigger" not in template:
                template["trigger"] = {"type": "MANUAL"}
            if "id" not in template:
                template["id"] = template_id
        return template

    def list_templates(self) -> List[Dict[str, Any]]:
        templates = self._load()
        result = []
        for tid, data in templates.items():
            # Ensure frontend-required fields exist for each template in the list
            if "name" not in data:
                data["name"] = tid
            if "trigger" not in data:
                data["trigger"] = {"type": "MANUAL"}
            if "id" not in data:
                data["id"] = tid
            result.append(data)
        return result
