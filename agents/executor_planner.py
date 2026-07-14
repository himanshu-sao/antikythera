"""
Executor Planner Module.
Handles decomposing spec and architecture into an actionable checklist.
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
        
        system_prompt = """You are the Antikythera Implementation Planner. 
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
            response_text = self.llm.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )

            # Ensure response is a string before cleaning
            if not isinstance(response_text, str):
                raise ValueError(f"Expected string from LLM, got {type(response_text)}")

            import json
            # Clean up response if LLM includes markdown
            clean_response = response_text.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response.split("```json")[1].split("```")[0].strip()
            elif clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1].split("```")[0].strip()

            checklist = json.loads(clean_response)
            # An empty/unusable-but-valid JSON (e.g. ``[]``) is NOT a plan.
            # Returning a placeholder checklist here (the old behaviour) let a
            # bad LLM call masquerade as a real plan, so the executor "succeeded"
            # on placeholders and wrote a stub execution_report.md (the P3.2
            # empty-report bug).  Fail loud instead: return [] and let
            # ExecutorAgent.execute() abort so executor_idea() -> 0 with a
            # FAILURE report (see agents/executor.py).
            if not isinstance(checklist, list) or not checklist:
                logger.error(
                    "Planner returned an empty/unusable checklist "
                    f"(parsed type={type(checklist).__name__}, len="
                    f"{len(checklist) if isinstance(checklist, list) else 'n/a'}); "
                    "refusing to substitute a stub plan — executor will abort."
                )
                return []
            logger.info(f"Successfully generated checklist with {len(checklist)} tasks.")
            return checklist
        except Exception as e:
            # Parser/LLM failure is also a fail-loud [] (NOT a stub checklist).
            logger.error(f"Failed to generate checklist: {str(e)}")
            logger.error(
                "Refusing to substitute a stub checklist after planner failure; "
                "executor will abort and write a FAILURE report."
            )
            return []
