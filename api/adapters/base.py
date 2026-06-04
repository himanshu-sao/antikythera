from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class AuthError(Exception):
    """Raised when authentication is required (HTTP 401)"""

class BaseAdapter(ABC):
    """
    Abstract Base Class for all external platform adapters.
    Ensures a consistent interface for the Operator Registry to call.
    """

    def __init__(self, vault):
        """
        Initialize with a vault instance for secure credential access.
        """
        self.vault = vault

    @abstractmethod
    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Fetch a resource from the external platform.
        """
        pass

    @abstractmethod
    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        """
        Update a resource on the external platform.
        """
        pass

    @abstractmethod
    async def create(self, payload: Dict[str, Any]) -> Any:
        """
        Create a new resource on the external platform.
        """
        pass

    @abstractmethod
    async def delete(self, resource_id: str) -> Any:
        """
        Delete a resource from the external platform.
        """
        pass