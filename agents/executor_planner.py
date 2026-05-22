"""
Executor Planner Module.
Handles decomposing specification and architecture into an actionable checklist.
"""

import os
import re
import logging
from typing import List, Dict, Any
from agents.llm_client import LLMClient

logger = logging.getLogger(__name__)

class ExecutorPlanner:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def create_checklist(self, spec_content: str, arch_content: str) -> List[Dict[str, Any]]:
        """
        Uses the LLM to generate a granular, atomic implementation checklist.
        """
        logger.info("Generating implementation checklist using LLM...")
        
        system_prompt = """You are the Hermes Implementation Planner. 
Your goal is to decompose a technical specification and architecture into a highly granular, atomic, and sequential implementation checklist.

### OBJECTIVE
Break down the implementation into the smallest possible actionable tasks. Each task must be atomic (e.g., "Create file X", "Implement function Y", "Add validation to Z").

### GUIDELINES
1. **Granularity**: Tasks should be small enough to be completed in a single step and verified easily.
2. **Sequence**: Tasks MUST be in a logical order (e.g., models -> utilities -> core logic -> API endpoints).
3. **Atomicity**: Each task should focus on one single responsibility.
4. **Verification-Ready**: Tasks should be phrased so they can be checked (e.g., "Ensure file X exists" or "Verify function Y handles error Z").
5. **Format**: Return the checklist as a valid JSON array of objects. Each object must have the following structure:
   {"task": "Description of the task", "type": "file_creation | code_implementation | dependency_install | verification"}

### OUTPUT FORMAT
Return ONLY a valid JSON array. No preamble, no markdown blocks.
Example:
[
  {"task": "Install dependency 'requests'", "type": "dependency_install"},
  {"task": "Create directory 'api/models'", "type": "file_creation"},
  {"task": "Implement User model in api/models/user.py", "type": "code_implementation"}
]
"""
        user_prompt = f"""
Based on the following Specification and Architecture, generate a detailed implementation checklist.

### SPECIFICATION:
{spec_content}

### ARCHITECTURE:
{arch_content}
"""
        try:
            response = self.llm.generate_structured_content(system_prompt, user_prompt)
            # Clean up response in case LLM included markdown blocks
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1].split("```")[0].strip()
            
            import json
            checklist = json.loads(clean_response)
            logger.info(f"Successfully generated checklist with {len(checklist)} tasks.")
            return checklist
        except Exception as e:
            logger.error(f"Failed to generate checklist: {str(e)}")
            # Fallback to a very minimal checklist if LLM fails
            return [
                {"task": "Initialize workspace", "type": "file_creation"},
                {"task": "Implement core logic", "type": "code_implementation"},
                {"task": "Run verification tests", "type": "verification"}
            ]
