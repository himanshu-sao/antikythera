import json
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from .models.automation import PathStep, Path, Pipeline, ExecutionMode
from .operator_registry import OperatorRegistry
from .session_state_manager import SessionStateManager
from agents.llm_client import LLMClient
# SecretVault removed – not used in this simplified flow
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
# No vault – OperatorRegistry instantiated without it
registry = OperatorRegistry(None)
# Shared LLM client. Resolves the UI-selected default provider/model from
# AIEngineConfigService (falling back to config.yaml) — no hardcoded key/model.
# Tests monkeypatch this module global with a fake LLMClient.
llm_client = LLMClient()
# For simplicity in this prototype, we use a global state manager.
# In production, this would be keyed by session_id.
session_state = SessionStateManager()

router = APIRouter()

# System prompt for the /propose LLM call. Phrased as standalone instructions
# so it works even for ibm_bob, which concatenates system+user into one query.
_PROPOSE_SYSTEM = (
    "You are the Antikythera Automation Architect. Translate the user's "
    "natural-language instruction into a single deterministic PathStep that the "
    "execution engine can run.\n"
    "Valid operator_id values: fetch_resource, update_resource, create_resource, "
    "delete_resource (mode ADAPTER); run_script (mode SCRIPT only).\n"
    "Valid mode values: ADAPTER, SCRIPT.\n"
    "Return a JSON object with keys: step_id (use \"step_new\"), operator_id, "
    "adapter_id, config (a JSON object), and optionally input_ref, output_ref, "
    "mode, condition, loop_over. Use the adapter_id hint provided in the user "
    "message unless the instruction clearly targets a different integration. "
    "Do not include any prose outside the JSON."
)


def _strip_code_fence(text: str) -> str:
    """Tolerate a fenced ```json block returned by the LLM."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else parts[0]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
        text = text.strip("`").strip()
    return text


def _propose_via_llm(request: "ProposalRequest") -> Optional["ProposalResponse"]:
    """Try to build the proposal from the shared LLM.

    Returns a ProposalResponse on success, or None when the LLM is unavailable
    / returns a stub / emits unparseable or invalid JSON — signaling the caller
    to fall back to the deterministic keyword logic.
    """
    instruction = request.instruction
    target_adapter = request.integration_id or (
        "jira_adapter" if "jira" in instruction.lower() else "github_adapter"
    )
    user_prompt = (
        f"Instruction: {instruction}\n"
        f"adapter_id hint: {target_adapter}\n"
        f"current_state: {json.dumps(request.current_state, default=str)}\n"
        "Produce the single best PathStep for this instruction as the JSON object "
        "described in the system instructions."
    )
    try:
        raw = llm_client.chat(_PROPOSE_SYSTEM, user_prompt)
    except Exception as e:  # LLMClient.chat never raises, but be defensive
        logger.debug(f"propose LLM call raised, falling back: {e}")
        return None

    if LLMClient.is_stub(raw):
        return None

    try:
        data = json.loads(_strip_code_fence(raw))
        if not isinstance(data, dict):
            return None
        # Require the PathStep mandatory fields.
        if not {"operator_id", "adapter_id", "config"}.issubset(data):
            return None
        data.setdefault("step_id", "step_new")
        data.setdefault("adapter_id", target_adapter)
        data.setdefault("mode", ExecutionMode.ADAPTER.value)
        step = PathStep(**data)
    except Exception as e:
        logger.debug(f"propose LLM JSON invalid, falling back: {e}")
        return None

    reasoning = data.get("reasoning") or f"LLM-proposed {step.operator_id} step."
    return ProposalResponse(
        proposal_id=f"prop_{len(request.current_state)}",
        suggested_step=step,
        reasoning=reasoning,
    )

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
    # The UI (AutomationStudio.tsx) already sends `model` in the request body;
    # Pydantic previously dropped it. Accepted now for forward-compat. NOTE: it
    # is not yet spliced into the chat call — the shared LLMClient owns model
    # selection (resolving the UI default / config.yaml). Reserved for a future
    # per-call override.
    model: Optional[str] = None

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
    """
    # Try the shared LLMClient first (UI-default provider/model). When no LLM
    # is configured / reachable / parseable, _propose_via_llm returns None and
    # we fall through to the deterministic keyword logic below so the UI keeps
    # working offline. See agents/llm_client.py LLMClient.chat for degradation.
    llm_proposal = _propose_via_llm(request)
    if llm_proposal is not None:
        return llm_proposal

    # Deterministic fallback — keyword/regex matching against the instruction.
    # MOCK AI LOGIC for demonstration of the flow:
    instruction = request.instruction.lower()
    current_state = request.current_state
    integration_id = request.integration_id

    # Use provided integration_id or guess from instruction
    target_adapter = integration_id if integration_id else ("jira_adapter" if "jira" in instruction else "github_adapter")
    
    # Enhanced logic to generate script steps and multi-choice proposals
    
    # Check for extract field commands
    if "extract" in instruction and ("field" in instruction or "data" in instruction):
        # Generate a parsing skill proposal
        # For simplicity, we'll propose a script step that uses regex to extract data
        # In a real implementation, this would trigger the Skill Brainstormer flow
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
        # Generate a conditional step proposal
        # For simplicity, we'll create a step with a condition
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
        # Generate a loop step proposal
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