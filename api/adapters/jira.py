import httpx
from typing import Any, Dict, Optional
import logging
from .base import BaseAdapter, AuthError

logger = logging.getLogger(__name__)

class JiraAdapter(BaseAdapter):
    """
    Adapter for Jira Cloud API.
    """
    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        # In real use, we would fetch the token from self.vault.get("JIRA_TOKEN")
        token = self.vault.get_secret("jira")
        if not token:
            logger.warning("Jira token not found in vault")
            raise AuthError("Jira token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('access_token')}" if token.get('access_token') else f"Bearer {token.get('token')}",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://your-domain.atlassian.net/rest/api/3/issue/{resource_id}",
                headers=headers,
                params=params
            )
            
            if response.status_code == 401:
                logger.warning("Jira API returned 401 Unauthorized")
                raise AuthError("Jira authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        token = self.vault.get_secret("jira")
        if not token:
            logger.warning("Jira token not found in vault")
            raise AuthError("Jira token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('access_token')}" if token.get('access_token') else f"Bearer {token.get('token')}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://your-domain.atlassian.net/rest/api/3/issue/{resource_id}",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 401:
                logger.warning("Jira API returned 401 Unauthorized")
                raise AuthError("Jira authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def create(self, payload: Dict[str, Any]) -> Any:
        token = self.vault.get_secret("jira")
        if not token:
            logger.warning("Jira token not found in vault")
            raise AuthError("Jira token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('access_token')}" if token.get('access_token') else f"Bearer {token.get('token')}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://your-domain.atlassian.net/rest/api/3/issue",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 401:
                logger.warning("Jira API returned 401 Unauthorized")
                raise AuthError("Jira authentication failed")
            
            response.raise_for_status()
            return response.json()

    async def delete(self, resource_id: str) -> Any:
        token = self.vault.get_secret("jira")
        if not token:
            logger.warning("Jira token not found in vault")
            raise AuthError("Jira token not found")
        
        headers = {
            "Authorization": f"Bearer {token.get('access_token')}" if token.get('access_token') else f"Bearer {token.get('token')}"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://your-domain.atlassian.net/rest/api/3/issue/{resource_id}",
                headers=headers
            )
            
            if response.status_code == 401:
                logger.warning("Jira API returned 401 Unauthorized")
                raise AuthError("Jira authentication failed")
            
            response.raise_for_status()
            return response.json()