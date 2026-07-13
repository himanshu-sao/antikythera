import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from .models.automation import Skill
from agents.llm_client import LLMClient
import os

logger = logging.getLogger(__name__)

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
os.makedirs(BASE_DIR, exist_ok=True)
# Dead SecretVault removed (P3.4 — skill_router half). main.py comments out
# SecretVault; credentials now come from env vars. This file no longer creates
# .vault.key / secrets.vault on disk as an import side effect.
# Shared LLM client. Resolves the UI-selected default provider/model from
# AIEngineConfigService (falling back to config.yaml) — no hardcoded key/model.
# Tests monkeypatch this module global with a fake LLMClient.
llm_client = LLMClient()
# Simple in-memory store for skills. In production, this would be a JSON file or DB.
skills_db: Dict[str, Skill] = {}

router = APIRouter()

# System prompt for the /brainstorm LLM call. Phrased as standalone instructions
# so it works even for ibm_bob, which concatenates system+user into one query.
_BRAINSTORM_SYSTEM = (
    "You are the Antikythera Skill Designer. Given a text sample, a list of "
    "target fields to extract, and an optional user suggestion, design a "
    "ready-to-use few-shot extraction prompt plus its output schema.\n"
    "Return a JSON object with keys:\n"
    "- proposed_prompt: a few-shot extraction prompt as a single string;\n"
    "- proposed_schema: an object mapping each target field name to a type "
    "string, one of string, number, boolean, array, object;\n"
    "- reasoning: a short string explaining the design.\n"
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


def _brainstorm_via_llm(request: "SkillProposalRequest") -> Optional["SkillProposalResponse"]:
    """Try to build the skill proposal from the shared LLM.

    Returns a SkillProposalResponse on success, or None when the LLM is
    unavailable / returns a stub / emits unparseable or invalid JSON —
    signaling the caller to fall back to the deterministic template builder.
    """
    user_prompt = (
        f"text_sample: {request.text_sample}\n"
        f"target_fields: {json.dumps(request.target_fields)}\n"
        f"suggestion: {request.suggestion}\n"
        "Produce the few-shot extraction prompt and schema as the JSON object "
        "described in the system instructions."
    )
    try:
        raw = llm_client.chat(_BRAINSTORM_SYSTEM, user_prompt)
    except Exception as e:  # LLMClient.chat never raises, but be defensive
        logger.debug(f"brainstorm LLM call raised, falling back: {e}")
        return None

    if not isinstance(raw, str) or "stub response" in raw.lower():
        return None

    try:
        data = json.loads(_strip_code_fence(raw))
        if not isinstance(data, dict):
            return None
        proposed_schema = data.get("proposed_schema")
        if not isinstance(proposed_schema, dict):
            return None
        proposed_prompt = data.get("proposed_prompt")
        reasoning = data.get("reasoning")
        if not isinstance(proposed_prompt, str) or not isinstance(reasoning, str):
            return None
    except Exception as e:
        logger.debug(f"brainstorm LLM JSON invalid, falling back: {e}")
        return None

    return SkillProposalResponse(
        proposed_prompt=proposed_prompt,
        proposed_schema=proposed_schema,
        reasoning=reasoning,
    )

class SkillProposalRequest(BaseModel):
    text_sample: str
    target_fields: List[str]
    suggestion: str

class SkillProposalResponse(BaseModel):
    proposed_prompt: str
    proposed_schema: Dict[str, Any]
    reasoning: str

@router.post("/brainstorm")
async def brainstorm_skill(request: SkillProposalRequest):
    """
    Interactive loop to create a few-shot prompt for a new skill.
    """
    # Try the shared LLMClient first (UI-default provider/model). When no LLM
    # is configured / reachable / parseable, _brainstorm_via_llm returns None
    # and we fall through to the deterministic template builder below so the UI
    # keeps working offline. See agents/llm_client.py LLMClient.chat degradation.
    llm_result = _brainstorm_via_llm(request)
    if llm_result is not None:
        return llm_result

    # Deterministic fallback — a hardcoded few-shot template built from the
    # sample and target fields. MOCK AI Logic preserved for the offline path.
    # Example: User provided a Jira description and wants to extract 'Remediation'
    sample = request.text_sample
    fields = request.target_fields

    prompt = f"You are a structured data extractor. Given the following text, extract the fields: {', '.join(fields)}.\n\n"
    prompt += "Example:\nText: 'Remediation: 2.5.0-1.el8_10'\nOutput: {{'remediation': '2.5.0-1.el8_10'}}\n\n"
    prompt += f"Now process this: {sample}"

    # Generate a simple schema based on the target fields
    schema = {f: "string" for f in fields}

    return SkillProposalResponse(
        proposed_prompt=prompt,
        proposed_schema=schema,
        reasoning=f"Created a few-shot prompt focusing on the extraction of {len(fields)} fields."
    )

@router.post("/save")
async def save_skill(skill: Skill):
    """
    Saves the finalized Skill to the store.
    """
    skills_db[skill.skill_id] = skill
    return {"status": "saved", "skill_id": skill.skill_id}

@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    if skill_id not in skills_db:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skills_db[skill_id]
