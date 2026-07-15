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
Break down the implementation into a SMALL number of actionable tasks. Aim for no more than 6 tasks; merge closely-related work into a single task rather than splitting exhaustively. Each task MUST be one that lands a concrete artifact: write/create a file, edit existing content, or install a dependency.

### DO NOT EMIT VERIFICATION TASKS
The executor cannot complete a verification-only task. Its only run-command tool is `terminal`, and a `terminal` (or `read_file`) call NEVER marks a task complete — only a non-stub `write_file` or a completed `patch` does. So a task like "Run pytest", "Run ls", "Verify the handler returns JSON", or "Check no db imports" is guaranteed to loop forever and fail the run. OMIT every such task entirely:
  - No abstract property-check ("Ensure the handler is read-only", "Verify no external imports", "Confirm the response is under N ms") — the spec captures those properties, not the plan.
  - No terminal-only check ("Run pytest ...", "Run ls ...", "Run python -c ...") even if phrased as a concrete command — there is no tool that can complete it.
  - No final "verification run" task. Verification of landed artifacts is the executor's own job, not a planner task.

Just emit the artifact-producing tasks and STOP. The executor self-verifies that each artifact it was asked to write actually landed; it does not need a verifier task to do that.

### ONE TASK PER FILE (no splitting one file across tasks)
Each distinct file must be produced by EXACTLY ONE task that writes its
COMPLETE final contents in a single `write_file`. Never split a single file
across multiple tasks — the executor's `write_file` OVERWRITES the whole file,
so a second task targeting the same path destroys the first. If a file has
several parts, write all of them in that one task's full contents and STOP.
Two tasks may share a target file name only if they name different files
(e.g. `api/a.py` and `api/b.py`), never the same path twice.

### GUIDELINES
1. **Bound the size**: Prefer fewer, slightly larger tasks over many micro-steps. Do NOT enumerate "create the directory", then "create the file", then "add the first line", then "add the second line" — those collapse into one "Create file X with <contents>" task. Each file appears in exactly ONE task; that task writes the entire file.
2. **Concrete artifact action only**: Every task maps to a tool that CAN complete it. Phrase tasks as concrete artifact ops: "Create file X with content Y", "Implement function Z in file F", "Install dependency D".
3. **Sequence**: Tasks in logical order (models -> utilities -> core logic -> API endpoints).
4. **Atomicity**: Each task focuses on one responsibility.
5. **Format**: Return the checklist as a valid JSON array of objects, each:
   {"task": "Concrete action description", "type": "file_creation | code_implementation | dependency_install"}
   The "verification" type is REMOVED — never emit it.

### OUTPUT FORMAT
Return ONLY a valid JSON array. No preamble, no markdown blocks. No trailing commentary.
Example:
[
  {"task": "Create api/models/user.py with the User model and fields", "type": "code_implementation"},
  {"task": "Implement POST /users handler in api/user_router.py", "type": "code_implementation"}
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
