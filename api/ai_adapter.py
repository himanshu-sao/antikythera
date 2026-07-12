import json
import logging
from typing import Dict, Any, List, Optional

from agents.llm_client import LLMClient

logger = logging.getLogger(__name__)

# System prompt framing the analyze() task as a decision engine that returns JSON.
_ANALYZER_SYSTEM = (
    "You are the Antikythera Cognitive Engine. Analyze the provided data and "
    "respond with a single JSON object containing the keys 'decision', "
    "'reasoning', and 'action_params'. Do not include any prose outside the JSON."
)


class AIAdapter:
    """
    Cognitive Adapter that uses an LLM to make decisions or analyze data.
    Implements the 'Self-Learning' loop by querying the PatternStore.

    The underlying LLM is the shared ``LLMClient``, which resolves the
    UI-selected default provider/model from ``AIEngineConfigService``. When no
    LLM is available (stub / API key missing / parse failure), ``analyze``
    falls back to the deterministic ``_simulate_llm_call`` so the pipeline
    never breaks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Args:
            api_key / model: legacy simulation params, retained only for
                backwards compatibility with tests that construct AIAdapter
                directly. They are no longer used to drive the LLM — the shared
                LLMClient resolves provider/model/keys from the config service.
            llm_client: an injectable LLMClient (used by tests). If omitted, a
                fresh config-service-resolved LLMClient is created lazily on
                first use so import-time failures don't break module load.
        """
        # Kept for back-compat inspection by older tests, but not used to call the LLM.
        self.api_key = api_key
        self.model = model
        self._llm_client = llm_client
        self._llm: Optional[LLMClient] = None

    def _get_llm(self) -> LLMClient:
        """Lazily construct the shared LLMClient (config-service resolved)."""
        if self._llm is None:
            self._llm = self._llm_client or LLMClient()
        return self._llm

    def analyze(
        self,
        prompt: str,
        context_data: Dict[str, Any],
        patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Performs cognitive analysis. Uses patterns for few-shot learning.

        Routes the analysis through the shared LLMClient and parses the JSON
        decision. If the LLM is unavailable, returns a stub response, or the
        response can't be parsed as JSON, falls back to the deterministic
        ``_simulate_llm_call`` so downstream steps always get a usable answer.
        """
        # Build the augmented prompt with learned patterns
        few_shot_examples = ""
        if patterns:
            few_shot_examples = "\n\nPrevious similar cases and how they were resolved:\n"
            for i, p in enumerate(patterns):
                few_shot_examples += (
                    f"Example {i+1}:\nContext: {json.dumps(p['context'])}\n"
                    f"Resolution: {p['resolution']}\n---\n"
                )

        full_prompt = (
            f"Current Context: {json.dumps(context_data)}\n"
            f"Task: {prompt}\n"
            f"Response Format: Return a JSON object with 'decision', "
            f"'reasoning', and 'action_params'."
        )

        user_prompt = f"{few_shot_examples}\n{full_prompt}"

        try:
            llm = self._get_llm()
            raw = llm.chat(system_prompt=_ANALYZER_SYSTEM, user_prompt=user_prompt)
        except Exception as e:
            logger.warning(f"LLMClient.chat raised, using simulated fallback: {e}")
            return self._simulate_llm_call(full_prompt, context_data)

        if not isinstance(raw, str) or "stub response" in raw.lower():
            # LLM unavailable / degraded to stub — use the deterministic fallback.
            return self._simulate_llm_call(full_prompt, context_data)

        # Expect a JSON object; tolerate a fenced ```json``` block.
        text = raw.strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else parts[0]
            if text.lstrip().lower().startswith("json"):
                text = text.lstrip()[4:]
            text = text.strip("`").strip()

        try:
            result = json.loads(text)
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"analyze() LLM response not JSON, using simulated fallback: {e}")
            return self._simulate_llm_call(full_prompt, context_data)

        if not isinstance(result, dict) or not {"decision", "reasoning"}.issubset(result):
            logger.debug("analyze() LLM JSON missing required keys, using simulated fallback")
            return self._simulate_llm_call(full_prompt, context_data)

        result.setdefault("action_params", {})
        return result

    def _simulate_llm_call(self, prompt: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic fallback used when no real LLM is available.

        Preserves the historical behavior: a 'vulnerability with no fix' context
        is flagged for security review; everything else continues.
        """
        text = json.dumps(context_data).lower()
        if "vulnerability" in text and "fix not available" in text:
            return {
                "decision": "SENSITIVE_BLOCK",
                "reasoning": "Vulnerability detected but no fix available. Requires security team manual review.",
                "action_params": {"assign_to": "security_lead", "priority": "critical"}
            }

        return {
            "decision": "CONTINUE",
            "reasoning": "No critical blockers found in data analysis.",
            "action_params": {}
        }
