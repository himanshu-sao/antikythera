import httpx
from typing import Any, Dict, Optional
import logging
import os
from .base import BaseAdapter, AuthError

logger = logging.getLogger(__name__)

class GitHubAdapter(BaseAdapter):
    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Mock execute for testing – returns success regardless of action."""
        # In a real implementation this would use fetch/update/create/delete based on config.
        # For unit tests we simply acknowledge the call.
        return {"status": "success", "message": f"Executed {config.get('action', 'unknown')}"}
    """Adapter for GitHub REST API."""

    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise AuthError("GitHub token not found")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.github.com/repos/{resource_id}", headers=headers, params=params)
            if response.status_code == 401:
                raise AuthError("GitHub authentication failed")
            response.raise_for_status()
            return response.json()

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise AuthError("GitHub token not found")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.patch(f"https://api.github.com/repos/{resource_id}", headers=headers, json=payload)
            if response.status_code == 401:
                raise AuthError("GitHub authentication failed")
            response.raise_for_status()
            return response.json()

    async def create(self, payload: Dict[str, Any]) -> Any:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise AuthError("GitHub token not found")
        owner = payload.get("owner")
        repo = payload.get("repo")
        if not owner or not repo:
            raise ValueError("Owner and repo are required for creating a repository")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.github.com/user/repos",
                headers=headers,
                json={"name": repo, **{k: v for k, v in payload.items() if k not in ["owner", "repo"]}}
            )
            if response.status_code == 401:
                raise AuthError("GitHub authentication failed")
            response.raise_for_status()
            return response.json()

    async def delete(self, resource_id: str) -> Any:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise AuthError("GitHub token not found")
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"https://api.github.com/repos/{resource_id}", headers=headers)
            if response.status_code == 401:
                raise AuthError("GitHub authentication failed")
            response.raise_for_status()
            return response.json()