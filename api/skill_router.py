from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from .models.automation import Skill
import os

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))
os.makedirs(BASE_DIR, exist_ok=True)
# Simple in-memory store for skills. In production, this would be a JSON file or DB.
skills_db: Dict[str, Skill] = {}

router = APIRouter()

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
    # MOCK AI Logic to generate a few-shot prompt based on a sample
    # In reality, this would be an LLM call.
    
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
