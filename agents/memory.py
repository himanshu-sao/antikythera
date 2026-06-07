import os
import logging
import glob
import datetime
from typing import List, Dict, Any, Optional
from agents.llm_client import LLMClient

logger = logging.getLogger(__name__)

# Using relative paths based on project structure
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "audit")
PATTERNS_FILE = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "patterns.md")

class MemoryAgent:
    def __init__(self, config_path: str):
        self.llm = LLMClient(config_path=config_path)

    def run_learning_loop(self):
        """
        Main loop for the Memory Agent.
        1. Collect audit logs.
        2. Extract patterns.
        3. Propose updates to patterns.md.
        """
        logger.info("Memory Agent starting learning loop...")
        
        audit_entries = self._collect_audit_entries()
        if not audit_entries:
            logger.info("No new audit entries found to learn from.")
            return

        logger.info(f"Collected {len(audit_entries)} audit entries.")
        
        patterns = self._analyze_patterns(audit_entries)
        if patterns:
            self._update_patterns_file(patterns)
        else:
            logger.info("No new patterns identified.")

    def _collect_audit_entries(self) -> List[str]:
        entries = []
        audit_files = sorted(glob.glob(os.path.join(AUDIT_DIR, "*.md")))
        for file_path in audit_files:
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                    parts = content.split("## ")
                    if len(parts) > 1:
                        entries.extend(parts[1:])
            except Exception as e:
                logger.error(f"Error reading audit file {file_path}: {str(e)}")
        return entries

    def _analyze_patterns(self, entries: List[str]) -> Optional[str]:
        logger.info("Analyzing entries for patterns...")
        system_prompt = """You are the Antikythera Memory Agent.
Your goal is to analyze audit logs and extract structured, reusable patterns.

### OBJECTIVE
Identify recurring themes in agent behavior, tech stack choices, naming conventions, and workflow patterns.

### OUTPUT FORMAT
Return ONLY a valid Markdown formatted section that can be appended or merged into patterns.md.
Use the following structure:

## [Category Name]
- **Pattern**: [Description]
- **Context**: [When to use]

### GUIDELINES
1. **Be Specific**: Don't just say "Python". Say "Preferred use of Python 3.9+ with type hinting".
2. **Be Actionable**: Patterns should be useful for future agents.
3. **Avoid Redundancy**: If a pattern already exists in the provided context, do not remember it.
"""
        user_prompt = f"Here are the recent audit log entries:\n\n{chr(10).join(entries)}\n\nBased on these entries, propose NEW patterns to add to the patterns.md file. If no new patterns are found, return an empty string."
        try:
            response_text = self.llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
            return response_text.strip()
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {str(e)}")
            return None

    def _update_patterns_file(self, new_patterns: str):
        logger.info("Updating patterns.md with new insights...")
        if not new_patterns or len(new_patterns.strip()) < 10:
            return
        try:
            timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            with open(PATTERNS_FILE, "a") as f:
                f.write(f"\n\n## Learned on {timestamp}\n\n")
                f.write(new_patterns)
            logger.info(f"Successfully updated {PATTERNS_FILE}")
        except Exception as e:
            logger.error(f"Failed to update patterns.md: {str(e)}")

def extract_pattern_from_content(item_id: str, artifact_name: str, content: str) -> bool:
    """
    Analyzes the provided artifact content to extract reusable patterns and updates patterns.md.
    """
    import logging
    from agents.llm_client import LLMClient
    import os
    from datetime import datetime

    logger = logging.getLogger(__name__)
    # Use project root for config and patterns file
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, 'config.yaml')
    brain_patterns = os.path.join(project_root, 'automation-ideas', 'brain', 'patterns.md')

    logger.info("Memory Agent: Extracting pattern from %s/%s", item_id, artifact_name)

    system_prompt = """
    You are the Antikythera Memory Agent. Your goal is to perform 'Pattern Promotion'.
    You will receive a successful technical artifact (spec, architecture, or test) from a completed automation task.
    Your job is to extract the underlying architectural, organizational, or operational patterns that made this task successful.

    Guidelines for Extraction:
    1. **Identify Reusable Logic**: Look for specific error handling strategies, security patterns, or structural elements.
    2. **Abstract the Pattern**: Do NOT include specific implementation details (like variable names or specific IDs). Instead, describe the *principle* of the pattern.
    3. **Format for patterns.md**: Output your findings as a new Markdown section with a clear heading and bullet points. Use a style that is easy for other AI agents to read as instructions.
    4. **Avoid Redundancy**: If a similar pattern already exists in the provided context, refine the existing pattern rather than duplicating it.

    Input format: [ARTIFACT TYPE] | [ARTIFACT CONTENT]
    Output format: A new Markdown section ready to be appended to patterns.md.
    """
    user_prompt = f"<{artifact_name.upper()}>\n{content}"

    try:
        # Using a more generic generate_structured_content if available, 
        # or falling back to chat
        llm = LLMClient(config_path=config_path)
        new_pattern_markdown = llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        
        if not new_pattern_markdown or len(new_pattern_markdown) < 50:
            logger.warning("Pattern extraction yielded insufficient content. Skipping.")
            return False

        if os.path.exists(brain_patterns):
            with open(brain_patterns, 'r') as f:
                current_content = f.read()
        else:
            current_content = "# Antikythera Architectural Patterns\n\n"

        with open(brain_patterns, 'w') as f:
            f.write(current_content + "\n" + new_pattern_markdown + "\n")

        logger.info("Successfully updated patterns.md with new pattern from %s", item_id)
        return True
    except Exception as e:
        logger.error("Pattern extraction failed for %s: %s", item_id, str(e))
        return False
