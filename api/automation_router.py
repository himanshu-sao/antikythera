from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
from .models.automation import PathStep, Path, Pipeline, ExecutionMode
from .operator_registry import OperatorRegistry
from .session_state_manager import SessionStateManager
from .secret_vault import SecretVault
import os
from functools import lru_cache

# Use the same base directory as main.py
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "automation-ideas"))

# Create vault instance (will create the directory if needed)
os.makedirs(BASE_DIR, exist_ok=True)
vault = SecretVault(BASE_DIR)
registry = OperatorRegistry(vault)
# For simplicity in this prototype, we use a global state manager. 
# In production, this would be keyed by session_id.
session_state = SessionStateManager()

router = APIRouter()

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
    # In a real implementation, this calls an LLM with a system prompt 
    # describing the OperatorRegistry and current state.
    
    # MOCK AI LOGIC for demonstration of the flow:
    instruction = request.instruction.lower()
    current_state = request.current_state
    
    # Enhanced logic to generate script steps and multi-choice proposals
    
    # Check for extract field commands
    if "extract" in instruction and ("field" in instruction or "data" in instruction):
        # Generate a parsing skill proposal
        # For simplicity, we'll propose a script step that uses regex to extract data
        # In a real implementation, this would trigger the Skill Brainstormer flow
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="run_script",
            adapter_id="jira_adapter",  # placeholder
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
            adapter_id="jira_adapter" if "jira" in instruction else "github_adapter",
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
            adapter_id="jira_adapter" if "jira" in instruction else "github_adapter",
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
            adapter_id="jira_adapter" if "jira" in instruction else "github_adapter",
            config={"params": {}},
            input_ref="resource_id",
            output_ref="fetched_data"
        )
        reasoning = "User wants to retrieve data. Mapping to fetch_resource operator."
    elif "update" in instruction or "change" in instruction:
        suggested_step = PathStep(
            step_id="step_new",
            operator_id="update_resource",
            adapter_id="jira_adapter" if "jira" in instruction else "github_adapter",
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

@router.post("/store-token")
# New endpoint to retrieve stored config values (e.g., Jira URL)
@router.get("/config/{service}")
async def get_config(service: str):
    """Return the stored secret (or config) for a given service name."""
    secret = vault.get_secret(service)
    if secret is None:
        raise HTTPException(status_code=404, detail="Config for service not found")
    return secret
async def store_token(request: TokenStorageRequest):
    """
    Store a token for a given service (jira, github) in the vault.
    """
    try:
        # Store the token as a dictionary with access_token key
        secret_data = {"access_token": request.token}
        vault.store_secret(request.service, secret_data)
        return {"status": "success", "message": f"Token for {request.service} stored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/state")
async def get_state():
    return session_state.export_state()