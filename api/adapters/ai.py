"""AI adapter: runs LLM analysis steps from workflow templates.

The template validator allows an ``ai`` adapter whose steps carry an
``analyze`` action (``{"adapter": "ai", "action": "analyze", "config":
{"prompt": ..., "context": ...}}``). The IntegrationHub's canonical-name
fallback resolves that adapter to this module, which delegates to the shared
``AIAdapter`` and therefore the UI-selected default provider/model.
"""

import logging
from typing import Any, Dict, List, Optional

from api.adapters.base import BaseAdapter

logger = logging.getLogger(__name__)


class AIAnalysisAdapter(BaseAdapter):
    """Thin adapter exposing ``analyze`` over the shared AIAdapter."""

    def __init__(self, vault: Optional[Any] = None):
        super().__init__(vault=vault)

    async def analyze(
        self,
        resource_id: Optional[str] = None,
        prompt: str = "",
        context: Optional[Dict[str, Any]] = None,
        patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        from api.ai_adapter import AIAdapter  # lazy: heavy import chain

        return AIAdapter().analyze(
            prompt or "",
            context or {},
            patterns or [],
        )

    # The CRUD verbs are not applicable to LLM analysis.
    async def fetch(self, resource_id: str, params: Optional[Dict[str, Any]] = None) -> Any:
        raise NotImplementedError("The ai adapter only supports the analyze action")

    async def update(self, resource_id: str, payload: Dict[str, Any]) -> Any:
        raise NotImplementedError("The ai adapter only supports the analyze action")

    async def create(self, payload: Dict[str, Any]) -> Any:
        raise NotImplementedError("The ai adapter only supports the analyze action")

    async def delete(self, resource_id: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        raise NotImplementedError("The ai adapter only supports the analyze action")
