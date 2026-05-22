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
        f.write(spec_content)
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
    
    system_prompt = f"""You are the Hermes Refiner Agent. Your goal is to transform simple automation ideas into professional, comprehensive, and actionable technical specifications.

Your output must be in valid Markdown format.

Follow these guidelines:
1. **Structure**: Use clear headings: # Specification for [ID]: [Title], ## Overview, ## Requirements (Functional/Non-Functional), ## Scope (In/Out), ## Edge Cases, ## Constraints, ## PII / Secret Handling Notes, and ## Dependencies.
2. **Detail**: Be highly specific. Instead of "handle errors", say "implement exponential backoff for transient network failures".
3. **Safety**: Always emphasize secret management (using env vars, not hardcoding) and idempotency.
4. **Patterns**: Incorporate the following architectural and organizational patterns from the system's brain:
{patterns_content if patterns_content else "No specific patterns provided."}

Your response should ONLY contain the markdown content for the specification document."""

    user_prompt = f"Refine this idea: '{title}' (ID: {idea_id})"

    try:
        spec_content = llm.generate_structured_content(system_prompt, user_prompt)
        write_spec(idea_id, spec_content)
        confidence = calculate_confidence(spec_content)
        logger.info("Refiner completed for %s with confidence %d", idea_id, confidence)
        return confidence
    except Exception as e:
        logger.error("LLM Refiner failed for %s: %s", idea_id, str(e))
        raise e

    return min(score, 100)


def refine_idea(idea_id, title, patterns_path=None):
    """
    Refine an idea from a one-liner into a full specification.

    Reads brain/patterns.md for context, generates a comprehensive spec,
    writes it to requirements/ID-XXX/spec.md, and returns a confidence score.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        title (str): The title/one-liner of the idea.
        patterns_path (str, optional): Path to brain/patterns.md.

    Returns:
        int: Confidence score (0-100).

    Raises:
        ValueError: If title is empty or None.
    """
    if not title or not title.strip():
        raise ValueError("Title cannot be empty")

    patterns_content = _read_patterns(patterns_path)
    spec_content = _generate_spec_content(idea_id, title, patterns_content)
    write_spec(idea_id, spec_content)
    confidence = calculate_confidence(spec_content)
    return confidence