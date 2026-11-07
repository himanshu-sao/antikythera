import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.llm_client import LLMClient
from api.ai_adapter import AIAdapter
from api.workflow_state_manager import WorkflowStateManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/builder", tags=["Workflow Builder"])

# Initialize dependencies
BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "automation-ideas")
state_manager = WorkflowStateManager(BASE_DIR)
# AIAdapter resolves the configured default provider/model from AIEngineConfigService
# via the shared LLMClient; no hardcoded key or model here.
ai_engine = AIAdapter()

_REQUIRED_TEMPLATE_KEYS = ("name", "trigger", "steps")

_GENERATION_SYSTEM = (
    "You are the Antikythera Blueprint Architect. Reply with ONE JSON object and nothing else. "
    "It must have the keys \"name\" (string), \"description\" (string), \"trigger\" (object with "
    "\"type\", \"provider\" and \"config\") and \"steps\" (a non-empty list). Each step has \"id\", "
    "\"adapter\" (one of internal, github, jira, ai), \"action\" (non-empty string naming the "
    "operation on that adapter), \"config\" (object) and \"board_stage\" (string). Do not add a "
    "\"type\" key to a step. Do not use a shell adapter. Do not wrap the JSON in prose."
)


class GenerationRequest(BaseModel):
    prompt: str = Field(..., min_length=10)
    template_name: Optional[str] = None


class TemplateValidationRequest(BaseModel):
    template_data: Dict[str, Any]


def _template_violations(template: Dict[str, Any]) -> List[str]:
    """Run the same adapter and config checks as POST /api/workflows/templates.

    Imported lazily: ``workflow_router`` imports ``api.main``, which includes this
    module, so a module-level import would be circular.
    """
    from api.workflow_router import _validate_step_configs, _validate_step_shape, _validate_template_adapters

    return (
        _validate_template_adapters(template)
        + _validate_step_shape(template)
        + _validate_step_configs(template)
    )


def _parse_template_reply(raw: Any) -> Optional[Dict[str, Any]]:
    """Return the template dict from an LLM reply, or None to fall back.

    Accepts a bare JSON object or one inside a ```json (or plain ```) fence. The
    object must have ``name``, ``trigger`` and ``steps``. Prose, stub text, a
    list root or a missing key all return None.
    """
    if not isinstance(raw, str) or LLMClient.is_stub(raw):
        return None
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    if not all(key in data for key in _REQUIRED_TEMPLATE_KEYS):
        return None
    return data


def _request_template_reply(prompt: str, context: Dict[str, Any]) -> Any:
    """Ask the configured LLM for a template and return the raw reply text.

    Goes through the adapter's shared LLMClient rather than ``analyze()``,
    because ``analyze()`` parses the reply into a decision dict and discards the
    template JSON this endpoint needs.
    """
    llm = ai_engine._get_llm()
    user_prompt = f"Context: {json.dumps(context)}\nRequest: {prompt}"
    return llm.chat(system_prompt=_GENERATION_SYSTEM, user_prompt=user_prompt)


def _fallback_template(request: GenerationRequest) -> Dict[str, Any]:
    """Deterministic templates used when no LLM reply is usable.

    Every template here uses only the allowlisted adapters (internal, github,
    jira, ai), has no shell step, and has step configs that match
    ADAPTER_CONFIG_SCHEMAS, so each one passes the save-time validators.
    """
    prompt_lower = request.prompt.lower()
    if "github" in prompt_lower and "merge" in prompt_lower:
        return {
            "name": request.template_name or "GitHub PR Review",
            "description": "Triggered on PR merge: reads the merged PR, summarises it and asks for sign-off.",
            "trigger": {"type": "webhook", "provider": "github", "config": {"event": "pull_request.closed"}},
            "steps": [
                {"id": 1, "adapter": "github", "action": "list_pull_requests",
                 "config": {"state": "closed"}, "board_stage": "EXECUTING"},
                {"id": 2, "adapter": "ai", "action": "analyze",
                 "config": {"prompt": "Summarise the merged pull request and flag any risk."},
                 "board_stage": "REVIEW_TEST"},
                {"id": 3, "adapter": "internal", "action": "add_comment",
                 "config": {"action": "add_comment", "body": "Release sign-off requested."},
                 "board_stage": "APPROVED"},
            ],
        }
    if "jira" in prompt_lower and "ticket" in prompt_lower:
        return {
            "name": request.template_name or "Jira Triage",
            "description": "Polls Jira for new tickets, classifies them and moves them on.",
            "trigger": {"type": "poll", "provider": "jira", "config": {"jql": "created > -1h", "interval": 60}},
            "steps": [
                {"id": 1, "adapter": "jira", "action": "list_tickets",
                 "config": {"jql": "created > -1h", "max_results": 50}, "board_stage": "INTAKE"},
                {"id": 2, "adapter": "ai", "action": "analyze",
                 "config": {"prompt": "Classify this ticket by urgency and component."},
                 "board_stage": "REFINEMENT"},
                {"id": 3, "adapter": "jira", "action": "update",
                 "config": {"transition": "Triage Done"}, "board_stage": "DONE"},
            ],
        }
    return {
        "name": request.template_name or "Custom Workflow",
        "description": "AI generated generic workflow.",
        "trigger": {"type": "webhook", "provider": "generic", "config": {}},
        "steps": [
            {"id": 1, "adapter": "ai", "action": "analyze",
             "config": {"prompt": request.prompt}, "board_stage": "REFINEMENT"},
            {"id": 2, "adapter": "internal", "action": "add_comment",
             "config": {"action": "add_comment", "body": "Workflow complete."}, "board_stage": "DONE"},
        ],
    }


@router.post("/generate", summary="Generate a workflow template from natural language")
async def generate_template(request: GenerationRequest):
    """
    AI-powered prompt-to-pipeline.
    Takes a description and returns a structured Template JSON. A usable LLM reply
    (a JSON object with name, trigger and steps) is returned as is; anything else
    (prose, stub text, an LLM error) falls back to a keyword template.
    """
    try:
        reply = _request_template_reply(request.prompt, {"requested_by": "user", "mode": "generation"})
    except Exception as exc:  # any LLM failure degrades to the fallback
        logger.warning("Blueprint generation LLM call failed, using fallback: %s", exc)
        reply = None

    template = _parse_template_reply(reply)
    if template is None:
        template = _fallback_template(request)
    return template


@router.post("/validate", summary="Validate a custom template structure")
async def validate_template(request: TemplateValidationRequest):
    data = request.template_data
    for key in _REQUIRED_TEMPLATE_KEYS:
        if key not in data:
            raise HTTPException(status_code=400, detail=f"Missing required field: {key}")

    if not isinstance(data["steps"], list) or len(data["steps"]) == 0:
        raise HTTPException(status_code=400, detail="Steps must be a non-empty list")

    # Same checks POST /api/workflows/templates applies at save time (B1/B2).
    violations: List[str] = _template_violations(data)
    if violations:
        return {
            "status": "invalid",
            "message": "Template failed validation: " + "; ".join(violations),
            "violations": violations,
        }
    return {"status": "valid", "message": "Template structure is correct", "violations": []}
