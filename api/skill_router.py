from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from .models.automation import Skill
from agents.llm_client import LLMClient
import json
import logging
import os

logger = logging.getLogger(__name__)

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
os.makedirs(BASE_DIR, exist_ok=True)
# Simple in-memory store for skills. In production, this would be a JSON file or DB.
skills_db: Dict[str, Skill] = {}

router = APIRouter()

# Shared LLM client, lazily constructed on first /brainstorm call so import-time
# or config-service failures don't break module load (mirrors AIAdapter._get_llm).
_llm: Optional[LLMClient] = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


# System prompt framing /brainstorm as a few-shot-prompt authoring engine that
# returns one JSON object with the SkillProposalResponse fields.
_BRAINSTORM_SYSTEM = (
    "You are the Antikythera Skill Brainstormer. Given a text sample, the target "
    "fields to extract, and a user suggestion, author a few-shot extraction "
    "prompt plus a JSON output schema keyed by the target fields. Respond with "
    "ONE JSON object — no prose outside the JSON — with the keys: "
    "proposed_prompt, proposed_schema, reasoning. proposed_schema MUST map every "
    "requested target field to a type (e.g. \"string\", \"number\"). Keep the "
    "prompt concise and self-contained."
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

    Routes through the shared ``LLMClient.chat()`` with a system prompt framing
    the LLM as a few-shot-prompt author. When the LLM is unavailable (no key /
    raise / stub / unparseable JSON), falls back to the deterministic few-shot
    template in ``_simulate_brainstorm`` so the loop never breaks — same
    contract as ``AIAdapter.analyze``.
    """
    user_prompt = (
        f"Text sample:\n{request.text_sample}\n\n"
        f"Target fields to extract: {', '.join(request.target_fields)}\n\n"
        f"User suggestion: {request.suggestion}\n\n"
        f"Produce proposed_prompt, proposed_schema (keys exactly matching the "
        f"target fields), and reasoning."
    )

    try:
        raw = _get_llm().chat(_BRAINSTORM_SYSTEM, user_prompt, temperature=0.2)
    except Exception as e:
        logger.warning("brainstorm_skill LLMClient.chat raised, using simulated fallback: %s", e)
        return _simulate_brainstorm(request)

    parsed = _strip_and_parse_json(raw)
    if parsed is None or not {
        "proposed_prompt", "proposed_schema", "reasoning",
    }.issubset(parsed):
        logger.debug("brainstorm_skill LLM response unparseable/incomplete, using simulated fallback")
        return _simulate_brainstorm(request)

    schema = parsed["proposed_schema"]
    if not isinstance(schema, dict) or not set(request.target_fields).issubset(schema):
        logger.debug("brainstorm_skill proposed_schema missing target fields, using simulated fallback")
        return _simulate_brainstorm(request)

    return SkillProposalResponse(
        proposed_prompt=parsed["proposed_prompt"],
        proposed_schema=schema,
        reasoning=parsed["reasoning"],
    )


def _simulate_brainstorm(request: SkillProposalRequest) -> SkillProposalResponse:
    """Deterministic fallback used when no real LLM is available.

    Preserves the historical /brainstorm behavior verbatim (the hardcoded
    few-shot-template string and the {field: \"string\"} schema), so
    degraded/test runs behave exactly as before the LLM wiring.
    """
    sample = request.text_sample
    fields = request.target_fields

    prompt = f"You are a structured data extractor. Given the following text, extract the fields: {', '.join(fields)}.\n\n"
    prompt += "Example:\nText: 'Remediation: 2.5.0-1.el8_10'\nOutput: {{'remediation': '2.5.0-1.el8_10'}}\n\n"
    prompt += f"Now process this: {sample}"

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
