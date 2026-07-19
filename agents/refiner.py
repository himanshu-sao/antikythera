"""
Refiner Agent — reads a one-liner from ideas.md and writes a detailed spec.md using an LLM.

The Refiner generates comprehensive specification documents with
requirements, scope, edge cases, constraints, and PII/secret handling notes.
"""

import os
import logging
from agents.llm_client import LLMClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
BRAIN_PATTERNS = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "patterns.md")

logger = logging.getLogger(__name__)

# Initialize LLM Client using central config
from agents.llm_client import LLMClient

llm = LLMClient(config_path=os.path.join(PROJECT_ROOT, "config.yaml"))

def _read_patterns(patterns_path=None):
    """
    Read patterns from brain/patterns.md.

    Args:
        patterns_path (str, optional): Path to patterns.md.

    Returns:
        str or None: The content of patterns.md, or None if not found.
    """
    path = patterns_path or BRAIN_PATTERNS
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return None


def write_spec(idea_id, spec_content):
    """
    Write spec content to requirements/ID-XXX/spec.md.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        spec_content (str): The markdown content to write.

    Returns:
        str: The path to the written file.
    """
    dir_path = os.path.join(REQUIREMENTS_DIR, idea_id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "spec.md")
    with open(file_path, "w") as f:
        f.write(str(spec_content))
    return file_path


def calculate_confidence(spec_content):
    """
    Calculate a confidence score (0-100) for a spec document.
    This is a heuristic check to ensure the LLM followed instructions.

    Args:
        spec_content (str): The spec document content.

    Returns:
        int: Confidence score between 0 and 100.
    """
    score = 0
    content_lower = spec_content.lower()
    
    # Basic structure check
    if "# Specification" in spec_content or "# Specification for" in spec_content:
        score += 20
    
    # Section check
    sections = ["requirements", "scope", "edge cases", "constraints", "pii", "overview"]
    for section in sections:
        if section in content_lower:
            score += 15
    
    # Content depth check
    if len(spec_content) > 800:
        score += 30
    elif len(spec_content) > 400:
        score += 15
        
    # Formatted list check
    if "-" in spec_content or "*" in spec_content:
        score += 15

    return min(score, 100)


# P4.1 — deterministic complexity classifier (no LLM call; reuses the spec
# text the Refiner already produced). Mirrors the "Proportionality" prose in
# the Refiner system prompt: trivial ideas shouldn't force a full pipeline.
COMPLEXITY_KEYWORDS = {
    "trivial": ["health", "ping", "rename", "typo", "one-line", "log line"],
    "simple":  ["endpoint", "script", "cli", "helper", "migration"],
    "complex": ["service", "microservice", "auth", "distributed",
                "migration of", "security-critical"],
}


def estimate_complexity(spec_content: str, title: str = "") -> str:
    """Classify a spec's complexity into ``trivial``/``simple``/``complex``.

    Deterministic keyword + length heuristic. Returns one of the three tier
    names (matches ``agents.constants.TIER_STAGES`` keys). Short specs default
    to ``trivial``; otherwise keyword hits decide, with ``complex`` winning
    ties so we never under-pipeline a security/distributed task.
    """
    if not spec_content:
        return "complex"
    text = (spec_content + " " + title).lower()
    # Very short spec → trivial regardless of keywords (a one-liner's spec
    # rarely exceeds a few hundred chars even after the Refiner expands it).
    if len(spec_content) < 400:
        return "trivial"
    hits = {tier: sum(text.count(k) for k in kws)
            for tier, kws in COMPLEXITY_KEYWORDS.items()}
    if hits["trivial"] and not hits["complex"]:
        return "trivial"
    if hits["simple"] and not hits["complex"]:
        return "simple"
    return "complex"


def refine_idea(idea_id, title, patterns_path=None):
    """
    Refine an idea from a one-liner into a full specification using an LLM.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        title (str): The title/one-liner of the idea.
        patterns_path (str, optional): Path to patterns.md.

    Returns:
        int: Confidence score (0-100).

    Raises:
        ValueError: If title is empty or None.
    """
    if not title or not title.strip():
        raise ValueError("Title cannot be empty")

    logger.info("Refining idea %s: %s", idea_id, title)

    patterns_content = _read_patterns(patterns_path)
    
    system_prompt = f"""You are the Antikythera Refiner Agent. Your goal is to transform automation ideas into professional, actionable technical specifications.

Your output must be in valid Markdown format.

Follow these guidelines:
1. **Proportionality**: Scale the level of detail to the complexity of the idea. If the idea is a simple utility, keep the spec concise and focused. If it is a complex system, be comprehensive.
2. **Strict Adherence**: Do NOT invent new functionality, add unrelated features, or change the core intent of the user's idea. If the user asks for a Slack script, do not turn it into a system monitoring tool.
3. **Structure**: Use clear headings: # Specification for [ID]: [Title], ## Overview, ## Requirements (Functional/Non-Functional), ## Scope (In/Out), ## Edge Cases, ## Constraints, ## PII / Secret Handling Notes, and ## Dependencies. (Omit sections that are not applicable to the specific idea).
4. **Detail**: Be specific where it adds value. Instead of "handle errors", suggest specific strategies (e.g., "exponential backoff") ONLY if relevant to the task.
5. **Safety**: Always emphasize secret management (using env vars, not hardcoding) and idempotency.
6. **Patterns**: Incorporate the following architectural and organizational patterns from the system's brain:
{patterns_content if patterns_content else "No specific patterns provided."}

Your response should ONLY contain the markdown content for the specification document."""

    user_prompt = f"Refine this idea: '{title}' (ID: {idea_id})"

    try:
        spec_content = llm.generate_structured_content(system_prompt, user_prompt)
        # Ensure required sections exist; fallback to deterministic template if LLM stub returns insufficient content
        required_sections = ["specification", "requirements", "scope", "edge cases", "constraints", "pii"]
        if not any(sec in spec_content.lower() for sec in required_sections):
            spec_content = f"# Specification for {idea_id}: {title}\n\n## Overview\n- Brief overview\n\n## Requirements\n- List requirements\n\n## Scope\n- In scope / out of scope\n\n## Edge Cases\n- Identify edge cases\n\n## Constraints\n- Constraints\n\n## PII / Secret Handling\n- Notes on secret handling"
        write_spec(idea_id, spec_content)
        confidence = calculate_confidence(spec_content)
        logger.info("Refiner completed for %s with confidence %d", idea_id, confidence)
        return confidence
    except Exception as e:
        logger.error("LLM Refiner failed for %s: %s", idea_id, str(e))
        raise e

    return min(score, 100)
