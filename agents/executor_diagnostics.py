"""
Executor Diagnostics Module.
Analyza error messages and suggests fixes or corrective actions.
"""

import logging
from typing import Optional
from agents.llm_client import LLMClient

logger = logging.getLogger(__name__)

class ExecutorDiagnostics:
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def diagnose_error(self, error_message: str, context: str) -> Optional[str]:
        """
        Analyzes an error message and context to suggest a fix.
        Returns a suggested command or a brief instruction.
        """
        logger.info("Analyzing error for diagnostics...")

        system_prompt = """You are the Antikythera Error Diagnostic Agent.
Your goal is to analyze error messages and provide a concise, actionable solution.

### OBJECTIVE
When an error occurs (e.g., a failed terminal command or a Python traceback), analyze the error and the current context to suggest the single most effective corrective action.

### GUIDELINES
1. **Conciseness**: Be extremely brief. Do not explain *why* it happened unless asked. Just tell the user *what to do*.
2. **Actionability**: The output should ideally be a single shell command or a very short instruction.
3. **Context Awareness**: Use the provided workspace context (files, current task) to make accurate suggestions.
4. **Format**: Return ONLY the suggested command or instruction. No preamble, no markdown.

### EXAMPLE OUTPUTS
- `pip install -r requirements.txt`
- `python -m pytest`
- `mkdir -p src/models`
- `import os; os.makedirs('data', exist_ok=True)`
- `Fix the syntax error in line 42 of main.py`
"""

        user_prompt = f"""
### ERROR MESSAGE:
{error_message}

### CURRENT CONTEXT:
{context}

### SUGGESTED FIX:
"""

        try:
            response_text = self.llm.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt
            )
            
            # Clean up response
            clean_response = response_text.strip()
            if clean_response.startswith("```"):
                # Remove markdown blocks if present
                clean_response = clean_response.split("\n")[0].replace("```", "").strip()
            
            logger.info(f"Diagnostic suggestion: {clean_response}")
            return clean_response

        except Exception as e:
            logger.error(f"Failed to diagnose error: {str(e)}")
            return None
