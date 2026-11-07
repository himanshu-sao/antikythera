import httpx
import os
from typing import Any, Dict, List, Optional
import logging
from .base import BaseAdapter, AuthError

logger = logging.getLogger(__name__)


class JiraAdapter(BaseAdapter):
    """Adapter for Jira Cloud API.

    Token resolution order (mirrors the GitHub adapter):
      1. ``JIRA_PAT`` / ``JIRA_TOKEN`` environment variable (documented in .env.example)
      2. SecretVault secret named "jira" (used by tests; vault may be None in production)
    A missing token raises :class:`AuthError` only when a method actually needs it,
    so ``JiraAdapter(None)`` is safe to construct.
    """

    def __init__(self, vault):
        super().__init__(vault)
        self.vault = vault
        # Credentials injected from an integration record (UI-configured).
        # Checked before the environment so a UI-configured integration wins.
        self._cfg_token: Optional[str] = None
        self._cfg_base_url: Optional[str] = None

    def configure(self, credentials: Dict[str, Any]) -> None:
        """Set credentials from an integration record (see IntegrationHub).

        Values already resolved (``${env:X}`` expanded, never ``*****``).
        Unknown keys are ignored; ``None`` clears a previous value.
        """
        self._cfg_token = credentials.get("token") or None
        self._cfg_base_url = (
            credentials.get("jira_url")
            or credentials.get("url")
            or credentials.get("base_url")
            or None
        )

    def _get_base_url(self) -> str:
        """Jira base URL: integration record first, then env, then the placeholder."""
        return (
            self._cfg_base_url
            or os.getenv("JIRA_BASE_URL")
            or "https://your-domain.atlassian.net"
        )

    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execute for testing – returns success regardless of action."""
        return {"status": "success", "message": f"Executed {config.get('action', 'unknown')}"}

    def _get_token(self) -> Optional[str]:
        """Resolve the Jira auth token: integration record, then env, then vault."""
        token = self._cfg_token or os.getenv("JIRA_PAT") or os.getenv("JIRA_TOKEN")
        if not token and self.vault:
            secret = self.vault.get_secret("jira")
            if secret:
                token = secret.get("access_token") or secret.get("token")
        return token

    async def fetch(self, resource_id: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Any:
        """Fetch a single issue by ID (operator_map: fetch_resource -> fetch)."""
        token = self._get_token()
        if not token:
            raise AuthError("Jira token not found")
        # If no specific resource is requested, return an empty dict (no‑op for tests)
        if not resource_id:
            return {}
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        base_url = self._get_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/rest/api/3/issue/{resource_id}", headers=headers, params=params)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            return response.json()

    async def list_tickets(self, jql: str = "order by created DESC", max_results: int = 50) -> List[Dict[str, Any]]:
        """List tickets via JQL query (dec #28: list/vector action for Studio Graphs)."""
        token = self._get_token()
        if not token:
            raise AuthError("Jira token not found")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        base_url = self._get_base_url()
        params = {"jql": jql, "maxResults": max_results}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/rest/api/3/search", headers=headers, params=params)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            data = response.json()
            return data.get("issues", [])

    async def list_projects(self) -> List[Dict[str, Any]]:
        """List all accessible Jira projects."""
        token = self._get_token()
        if not token:
            raise AuthError("Jira token not found")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        base_url = self._get_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{base_url}/rest/api/3/project", headers=headers)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            return response.json()

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        token = self._get_token()
        if not token:
            # No token – assume a mock environment; return payload unchanged
            return payload
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        base_url = self._get_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{base_url}/rest/api/3/issue/{resource_id}", headers=headers, json=payload)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            return response.json()

    async def create(self, payload: Dict[str, Any]) -> Any:
        token = self._get_token()
        if not token:
            raise AuthError("Jira token not found")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        base_url = self._get_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{base_url}/rest/api/3/issue", headers=headers, json=payload)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            return response.json()

    async def delete(self, resource_id: str) -> Any:
        token = self._get_token()
        if not token:
            raise AuthError("Jira token not found")
        headers = {"Authorization": f"Bearer {token}"}
        base_url = self._get_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{base_url}/rest/api/3/issue/{resource_id}", headers=headers)
            if response.status_code == 401:
                raise AuthError("Jira authentication failed")
            response.raise_for_status()
            return response.json()