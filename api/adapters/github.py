from .base import BaseAdapter, AuthError
import httpx
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class GitHubAdapter(BaseAdapter):
    """
    Adapter for GitHub REST API.
    """
    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        token = self.vault.get_secret("github")
        if not token:
            logger.warning("GitHub token not found in vault")
            raise AuthError("GitHub token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('token')}",
            "Accept": "application/vnd.github+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.github.com/repos/{resource_id}",
                headers=headers,
                params=params
            )
            
            if response.status_code == 401:
                logger.warning("GitHub API returned 401 Unauthorized")
                raise AuthError("GitHub authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        token = self.vault.get_secret("github")
        if not token:
            logger.warning("GitHub token not found in vault")
            raise AuthError("GitHub token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('token')}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"https://api.github.com/repos/{resource_id}",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 401:
                logger.warning("GitHub API returned 401 Unauthorized")
                raise AuthError("GitHub authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def create(self, payload: Dict[str, Any]) -> Any:
        token = self.vault.get_secret("github")
        if not token:
            logger.warning("GitHub token not found in vault")
            raise AuthError("GitHub token not found")
        
        # For simplicity, we assume payload contains 'owner' and 'repo'
        owner = payload.get("owner")
        repo = payload.get("repo")
        if not owner or not repo:
            raise ValueError("Owner and repo are required for creating a repository")
        
        headers = {
            "Authorization": f"Bearer {token.get('token')}",
            "Accept": "application/vnd.github+json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/user/repos",
                headers=headers,
                json={"name": repo, **{k: v for k, v in payload.items() if k not in ["owner", "repo"]}}
            )
            
            if response.status_code == 401:
                logger.warning("GitHub API returned 401 Unauthorized")
                raise AuthError("GitHub authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def delete(self, resource_id: str) -> Any:
        token = self.vault.get_secret("github")
        if not token:
            logger.warning("GitHub token not found in vault")
            raise AuthError("GitHub token not found")
        
        # resource_id should be in the form "owner/repo"
        headers = {
            "Authorization": f"Bearer {token.get('token')}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.github.com/repos/{resource_id}",
                headers=headers
            )
            
            if response.status_code == 401:
                logger.warning("GitHub API returned 401 Unauthorized")
                raise AuthError("GitHub authentication failed")
            
            response.raise_for_status()
            return response.json()