from typing import Dict, Any
from api.adapters.base import BaseAdapter
import uuid

class JiraAdapter(BaseAdapter):
    """Adapter for interacting with the Jira API."""

    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Required: 'site' (e.g., 'company.atlassian.net')
        if "site" not in config:
            return False
        return True

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # Simulated Jira API behavior
        action = config.get("action")
        site = config.get("site")
        
        if action == "create_issue":
            summary = config.get("summary", "New Issue")
            return {
                "status": "success", 
                "message": f"Created issue in {site}",
                "external_id": f"JIRA-{uuid.uuid4().hex[:4].upper()}"
            }
        elif action == "transition_issue":
            issue_key = config.get("issue_key")
            status = config.get("status")
            return {
                "status": "success", 
                "message": f"Transitioned {issue_key} to {status}"
            }
        
        return {"status": "error", "message": f"Unsupported Jira action: {action}"}

    def check_status(self, run_id: str, config: Dict[str, Any]) -> str:
        return "COMPLETED"
