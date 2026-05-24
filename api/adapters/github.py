from typing import Dict, Any
from api.adapters.base import BaseAdapter
import uuid

class GitHubAdapter(BaseAdapter):
    """Adapter for interacting with the GitHub API."""

    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Required: 'repo' (e.g., 'owner/repo')
        if "repo" not in config:
            return False
        return True

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # In a production system, this would use requests/httpx to call GitHub API
        # Here, we simulate the behavior.
        action = config.get("action")
        repo = config.get("repo")
        
        if action == "create_comment":
            body = config.get("body", "Comment from Antikythera")
            issue_id = config.get("issue_id")
            return {
                "status": "success", 
                "message": f"Created comment on {repo} issue {issue_id}",
                "external_id": f"gh_com_{uuid.uuid4().hex[:6]}"
            }
        elif action == "set_status":
            state = config.get("state", "success")
            sha = config.get("sha")
            return {
                "status": "success", 
                "message": f"Set status to {state} for SHA {sha}"
            }
        
        return {"status": "error", "message": f"Unsupported GitHub action: {action}"}

    def check_status(self, run_id: str, config: Dict[str, Any]) -> str:
        # GitHub actions are usually synchronous for these operations
        return "COMPLETED"
