from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseAdapter(ABC):
    """Base class for all external integration adapters."""

    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Ensures the adapter has all required parameters in its config."""
        pass

    @abstractmethod
    def execute(self, run_id: str, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Performs the actual API call and returns a standardized result."""
        pass

    @abstractmethod
    def check_status(self, run_id: str, config: Dict[str, Any]) -> str:
        """Returns the status of an async action: 'PENDING', 'COMPLETED', or 'FAILED'."""
        pass
