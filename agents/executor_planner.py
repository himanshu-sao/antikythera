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

# Hard cap on how many tasks a planner checklist may contain.  A live LLM run
# (P3.2.6) saw the planner decompose a 2-file health endpoint idea into 11
# tasks; at 5 retries × multi-turn per task that balloons the live run past
# the time budget, and smaller models stumble on the abstract/meta tail tasks.
# Cap the plan at a size the executor can realistically close, keeping the
# most atomic, tool-actionable items.  Truncation keeps the leading tasks in
# sequence (the planner emits logically-ordered files -> core -> endpoints).
MAX_TASKS = 6

class ExecutorPlanner:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def create_checklist(self, spec_content: str, arch_content: str) -> List[Dict[str, Any]]:
        """
        Uses the LLM to generate a granular, atomic implementation checklist.
        """
        logger.info("Generating implementation checklist using LLM...")
        
        system_prompt = """You are the Antikythera Implementation Planner.
Your goal is to decompose a technical specification and architecture into a granular, atomic, and sequential implementation checklist.

### OBJECTIVE
Break down the implementation into a SMALL number of actionable tasks. Aim for no more than 6 tasks; merge closely-related work into a single task rather than splitting exhaustively. Each task must be a concrete action one of the executor tools can perform (write/create a file, edit existing content, install a dependency, or run a verification command).

### GUIDELINES
1. **Bound the size**: Prefer fewer, slightly larger tasks over many micro-steps. Do NOT enumerate "create the directory", then "create the file", then "add the first line", then "add the second line" — those collapse into one "Create file X with <contents>" task.
2. **Concrete action, not abstract property**: Every task must map to a tool action. Tasks like "Ensure the handler returns JSON" or "Verify no db imports" are abstract property-checks with no concrete tool action — OMIT them entirely; the spec itself captures required properties. Phrase tasks as concrete ops: "Create file X with content Y", "Implement function Z in file F", "Install dependency D", "Run pytest tests/test_foo.py".
3. **Sequence**: Tasks in logical order (models -> utilities -> core logic -> API endpoints -> one final verification run).
4. **Atomicity**: Each task focuses on one responsibility.
5. **Final task only**: At most ONE verification task at the end (e.g., "Run pytest tests/test_foo.py"), phrased as the concrete command to run — never an abstract "verify the code is correct".
6. **Format**: Return the checklist as a valid JSON array of objects, each:
   {"task": "Concrete action description", "type": "file_creation | code_implementation | dependency_install | verification"}

### OUTPUT FORMAT
Return ONLY a valid JSON array. No preamble, no markdown blocks. No trailing commentary.
Example:
[
  {"task": "Create api/models/user.py with the User model and fields", "type": "code_implementation"},
  {"task": "Run pytest tests/test_user.py", "type": "verification"}
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
            # Cap the plan at MAX_TASKS.  A live run (P3.2.6) saw a 2-file idea
            # become 11 tasks and time out; the executor closes far more reliably
            # on a bounded plan.  Keep the leading tasks (planner emits in
            # logical sequence) and drop the rest.  This is a plan-size guard,
            # not a stub substitution — the kept tasks are the planner's real work.
            if len(checklist) > MAX_TASKS:
                logger.warning(
                    "Planner produced %d tasks; capping to %d (keeping the first "
                    "%d in sequence). See MAX_TASKS.", len(checklist), MAX_TASKS, MAX_TASKS
                )
                checklist = checklist[:MAX_TASKS]
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
