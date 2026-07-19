from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
import json
import logging
from typing import Any, Dict, Optional, List
from .models.automation import PathStep, Path, Pipeline, ExecutionMode
from .operator_registry import OperatorRegistry
from agents.llm_client import LLMClient
from .session_state_manager import SessionStateManager
# SecretVault removed – not used in this simplified flow
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
# No vault – OperatorRegistry instantiated without it
registry = OperatorRegistry(None)
# For simplicity in this prototype, we use a global state manager.
# In production, this would be keyed by session_id.
session_state = SessionStateManager()

router = APIRouter()

# Shared LLM client, lazily constructed on first /propose call so import-time
# or config-service failures don't break module load (mirrors AIAdapter._get_llm).
_llm: Optional[LLMClient] = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


# System prompt framing /propose as a translation engine that returns one JSON
# object. Keys mirror PathStep fields (api/models/automation.py) plus a leading
# "reasoning" so the UI can show why the step was proposed.
_PROPOSER_SYSTEM = (
    "You are the Antikythera Automation Compiler. Translate a natural-language "
    "instruction into a single PathStep proposal for a deterministic Kanban "
    "pipeline. Respond with ONE JSON object — no prose outside the JSON — with "
    "the keys: step_id, operator_id, adapter_id, mode, config, input_ref, "
    "output_ref, condition, loop_over, reasoning. operator_id MUST be one of: "
    "fetch_resource, update_resource, run_script. mode is \"adapter\" or "
    "\"script\". config is an object of operator params. condition is null or an "
    "object {type, field, value}. loop_over is null or an object "
    "{source, iterator_var}. Keep step_id as \"step_new\"."
)


def _strip_and_parse_json(raw: str) -> Optional[dict]:
    """Tolerantly parse an LLM response as a JSON object (handles ```json fences).

    Returns None for stub responses, non-JSON text, or non-object JSON — callers
    fall back to the deterministic simulation. Mirrors AIAdapter.analyze parsing.
    """
    if not isinstance(raw, str) or "stub response" in raw.lower():
        return None
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip("`").strip()
    try:
        result = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return result if isinstance(result, dict) else None

@router.get("/templates")
async def get_templates():
    """Return a list of available automation templates (static placeholder)."""
    templates = [
        {"name": "GitHub Issue Sync", "description": "Sync issues between repos"},
        {"name": "Jira Ticket Automation", "description": "Create Jira tickets from chat commands"},
        {"name": "File Watcher", "description": "Monitor a directory and trigger actions"},
    ]
    return {"templates": templates}


class ProposalRequest(BaseModel):
    instruction: str
    current_state: Dict[str, Any]
    path_id: Optional[str] = None
    integration_id: Optional[str] = None

class ProposalResponse(BaseModel):
    proposal_id: str
    suggested_step: PathStep
    reasoning: str

class AcceptProposalRequest(BaseModel):
    proposal_id: str
    step: PathStep

class TokenStorageRequest(BaseModel):
    service: str  # e.g., "jira", "github"
    token: str

@router.post("/propose", response_model=ProposalResponse)
async def propose_step(request: ProposalRequest):
    """
    AI-driven proposal loop.
    Translates natural language to a deterministic PathStep.

    Routes through the shared ``LLMClient.chat()`` with a system prompt
    describing the OperatorRegistry operators and the current pipeline state.
    When the LLM is unavailable (no key / raise / stub / unparseable JSON),
    falls back to the deterministic simulation in ``_simulate_propose`` so the
    proposal loop never breaks — same contract as ``AIAdapter.analyze``.
    """
    instruction = request.instruction.lower()
    current_state = request.current_state
    integration_id = request.integration_id

    # Use provided integration_id or guess from instruction (unchanged heuristic).
    target_adapter = integration_id if integration_id else (
        "jira_adapter" if "jira" in instruction else "github_adapter"
    )

    user_prompt = (
        f"Instruction: {request.instruction}\n"
        f"Target adapter: {target_adapter}\n"
        f"Current pipeline state: {json.dumps(current_state)}\n"
        f"Available operators: fetch_resource (read a resource via the "
        f"adapter), update_resource (modify a resource via the adapter), "
        f"run_script (execute an inline Python snippet). Choose operator_id "
        f"and mode accordingly, then fill config/input_ref/output_ref. "
        f"Prefer mode=\"adapter\" unless the instruction asks to extract or "
        f"transform data (then mode=\"script\" with a run_script code snippet)."
    )

    try:
        raw = _get_llm().chat(_PROPOSER_SYSTEM, user_prompt, temperature=0.2)
    except Exception as e:
        logger.warning("propose_step LLMClient.chat raised, using simulated fallback: %s", e)
        return _simulate_propose(request)

    parsed = _strip_and_parse_json(raw)
    if parsed is None or not {
        "step_id", "operator_id", "adapter_id", "config",
    }.issubset(parsed):
        logger.debug("propose_step LLM response unparseable/incomplete, using simulated fallback")
        return _simulate_propose(request)

    # Coerce the LLM JSON into a valid PathStep, allowing the model to return
    # only the fields it filled. `mode` may arrive as a string ("adapter"/"script").
    try:
        mode = parsed.get("mode", ExecutionMode.ADAPTER)
        if isinstance(mode, str):
            mode = ExecutionMode(mode)
        suggested_step = PathStep(
            step_id=parsed.get("step_id", "step_new"),
            operator_id=parsed["operator_id"],
            adapter_id=parsed.get("adapter_id", target_adapter),
            mode=mode,
            config=parsed.get("config", {}) or {},
            input_ref=parsed.get("input_ref"),
            output_ref=parsed.get("output_ref"),
            condition=parsed.get("condition"),
            loop_over=parsed.get("loop_over"),
        )
    except (TypeError, ValueError) as e:
        logger.debug("propose_step LLM JSON produced an invalid PathStep (%s), using simulated fallback", e)
        return _simulate_propose(request)

    reasoning = parsed.get("reasoning") or "LLM-proposed PathStep."
    return ProposalResponse(
        proposal_id=f"prop_{len(current_state)}",
        suggested_step=suggested_step,
        reasoning=reasoning,
    )


def _simulate_propose(request: ProposalRequest) -> ProposalResponse:
    """Deterministic fallback used when no real LLM is available.

    Preserves the historical /propose behavior verbatim (the four regex/keyword
    branches plus the 400 for unknown instructions), so degraded/test runs behave
    exactly as before the LLM wiring.
    """
    instruction = request.instruction.lower()
    current_state = request.current_state
    integration_id = request.integration_id

    target_adapter = integration_id if integration_id else ("jira_adapter" if "jira" in instruction else "github_adapter")

    # Check for extract field commands
    if "extract" in instruction and ("field" in instruction or "data" in instruction):
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="run_script",
            adapter_id=target_adapter,  # use selected integration
            mode=ExecutionMode.SCRIPT,
            config={
                "code": '''import re
# Extract structured data from text
text = "{{input_text}}"  # This would be replaced with actual input_ref resolution
patterns = {
    "image": r'us\\.icr\\.io/[^\\s]+',
    "os_distro": r'red hat enterprise linux\\s*[0-9]+\\.?[0-9]*',
    "java_path": r'/opt/ibm/java/jre/bin/java'
}
extracted = {}
for key, pattern in patterns.items():
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        extracted[key] = match.group(0)
# Output extracted fields
result = extracted'''
            },
            input_ref=None,  # Would be set based on context
            output_ref="extracted_fields"
        )
        reasoning = "User wants to extract structured data. Proposing a script step with regex patterns."
        return ProposalResponse(
            proposal_id=f"prop_{len(current_state)}",
            suggested_step=suggested_step,
            reasoning=reasoning
        )

    # Check for conditional instructions
    if "if" in instruction and ("then" in instruction or "update" in instruction):
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="update_resource",
            adapter_id=target_adapter,
            mode=ExecutionMode.ADAPTER,
            config={"status": "Investigating"},
            input_ref=None,
            output_ref="update_result",
            condition={
                "type": "equals",
                "field": "extracted_fields.os_distro",
                "value": "RHEL8"
            }
        )
        reasoning = "User wants to perform a conditional update. Proposing a step with a condition."
        return ProposalResponse(
            proposal_id=f"prop_{len(current_state)}",
            suggested_step=suggested_step,
            reasoning=reasoning
        )

    # Check for loop instructions
    if "each" in instruction or "all" in instruction or "every" in instruction:
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="fetch_resource",
            adapter_id=target_adapter,
            mode=ExecutionMode.ADAPTER,
            config={"params": {}},
            input_ref=None,
            output_ref="fetched_data",
            loop_over={
                "source": "fetched_data",  # Assuming we have a list from previous step
                "iterator_var": "item"
            }
        )
        reasoning = "User wants to process each item. Proposing a step with loop_over."
        return ProposalResponse(
            proposal_id=f"prop_{len(current_state)}",
            suggested_step=suggested_step,
            reasoning=reasoning
        )

    # Existing logic for fetch and update
    if "fetch" in instruction or "get" in instruction:
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="fetch_resource",
            adapter_id=target_adapter,
            config={"params": {}},
            input_ref="resource_id",
            output_ref="fetched_data"
        )
        reasoning = "User wants to retrieve data. Mapping to fetch_resource operator."
    elif "update" in instruction or "change" in instruction:
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="update_resource",
            adapter_id=target_adapter,
            config={"status": "Investigating"},
            input_ref="fetched_data",
            output_ref="update_result"
        )
        reasoning = "User wants to modify a resource. Mapping to update_resource operator."
    else:
        # Fallback for unknown instructions
        raise HTTPException(status_code=400, detail="I'm not sure how to translate that to a deterministic step. Could you be more specific?")

    return ProposalResponse(
        proposal_id=f"prop_{len(current_state)}",
        suggested_step=suggested_step,
        reasoning=reasoning
    )

@router.post("/accept")
async def accept_proposal(request: AcceptProposalRequest):
    """
    Executes the accepted proposal in the sandbox and saves it to the Path.
    """
    step = request.step
    
    # 1. Execute in sandbox
    try:
        result = await registry.execute_step(step.dict(), session_state.state)
        
        # 2. Store output in state
        if step.output_ref:
            session_state.set_value(step.output_ref, result)
            
        return {
            "status": "success",
            "executed_result": result,
            "current_state": session_state.export_state()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Token storage endpoints removed – credentials are now provided via environment variables and integration config placeholders
@router.get("/state")
async def get_state():
    return session_state.export_state()