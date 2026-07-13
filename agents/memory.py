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
# Additional paths used by the brain‑loop tests
PENDING_UPDATES_FILE = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "pending-updates.md")
HISTORY_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "history")


def _is_stub_response(text: Any) -> bool:
    """Detect unusable LLM output (delegates to ``LLMClient.is_stub``).

    Centralized contract — ``LLMClient.is_stub()`` is the single source of
    truth for stub detection. ``api/automation_router.py``,
    ``api/skill_router.py``, and ``api/ai_adapter.py`` also call it directly.

    Returning ``True`` means "skip the write".
    """
    return LLMClient.is_stub(text)


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
        except Exception as e:
            logger.error(f"Failed to analyze patterns: {str(e)}")
            return None
        # P3.1 stub-guard: never let a degraded stub / empty "no patterns" reply
        # reach patterns.md as a ``## Learned on …`` section. When the LLM is
        # unreachable, LLMClient.chat() returns "[stub response — …]"; we log
        # the reason (it carries the real failure cause) and skip this round.
        if _is_stub_response(response_text):
            logger.warning(
                "Memory loop produced no usable patterns; skipping patterns.md "
                "write. LLM reason: %r", response_text
            )
            return None
        return response_text.strip()

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
    Returns True if a new pattern was added, False otherwise.
    """
    import logging
    from agents.llm_client import LLMClient
    import os
    from datetime import datetime

    logger = logging.getLogger(__name__)
    # Resolve paths relative to the project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config.yaml")
    # Use the module-level constant so tests can patch one PATTERNS_FILE and
    # affect both write-paths (this matches _update_patterns_file, which already
    # uses the constant). Hardcoding a parallel path here previously meant the
    # on-completion promotion wrote to a path tests could not redirect.
    brain_patterns = PATTERNS_FILE

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
        llm = LLMClient(config_path=config_path)
        new_pattern_markdown = llm.chat(system_prompt=system_prompt, user_prompt=user_prompt)
        # P3.1 stub-guard: a degraded stub or empty "no patterns" reply must not
        # be appended to patterns.md (same contract as the periodic loop above
        # and the routers/AIAdapter). Log the reason and skip.
        if _is_stub_response(new_pattern_markdown):
            logger.warning(
                "Pattern extraction for %s/%s produced no usable content; "
                "skipping patterns.md write. LLM reason: %r",
                item_id, artifact_name, new_pattern_markdown,
            )
            return False
        # If the LLM returns insufficient content, skip
        if len(new_pattern_markdown) < 50:
            logger.warning("Pattern extraction yielded insufficient content. Skipping.")
            return False
        # Append the new pattern to patterns.md (create file if missing)
        os.makedirs(os.path.dirname(brain_patterns), exist_ok=True)
        with open(brain_patterns, "a") as f:
            f.write("\n\n" + new_pattern_markdown + "\n")
        logger.info("Successfully updated patterns.md with new pattern from %s", item_id)
        return True
    except Exception as e:
        logger.error(f"Pattern extraction failed for {item_id}: {e}")
        return False

def analyze_and_propose() -> bool:
    """Entry point used by the brain loop.
    Instantiates a MemoryAgent with the default config and runs its learning loop.
    Returns True if the loop completed without raising, otherwise False.
    """
    try:
        # Use environment variable for config path if provided, otherwise default
        config_path = os.getenv(
            "AGENT_CONFIG_PATH",
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.yaml",
            ),
        )
        agent = MemoryAgent(config_path=config_path)
        agent.run_learning_loop()
        return True
    except Exception as e:
        logger.error(f"MemoryAgent analyze_and_propose failed: {e}")
        return False

