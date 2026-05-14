"""
Refiner Agent — reads a one-liner from ideas.md and writes a detailed spec.md.

The Refiner generates comprehensive specification documents with
requirements, scope, edge cases, constraints, and PII/secret handling notes.
"""

import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
BRAIN_PATTERNS = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "patterns.md")


def _generate_spec_content(idea_id, title, patterns_content=None):
    """
    Generate a comprehensive specification document.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        title (str): The title of the idea.
        patterns_content (str, optional): Content from brain/patterns.md.

    Returns:
        str: The generated spec markdown content.
    """
    patterns_section = ""
    if patterns_content and patterns_content.strip():
        patterns_section = f"""
## Patterns Referenced

The following patterns from `brain/patterns.md` were considered during refinement:

{patterns_content[:500]}

"""

    return f"""# Specification for {idea_id}: {title}

## Overview

{title} is an automation task that aims to streamline and improve operational efficiency. This specification outlines the requirements, scope, constraints, and considerations for implementing this automation.

## Requirements

### Functional Requirements
- The system shall automate the core workflow described in "{title}"
- The automation shall execute without manual intervention once triggered
- The system shall log all actions and outcomes for audit purposes
- Error handling shall be implemented for all failure modes
- The automation shall respect existing system constraints and permissions

### Non-Functional Requirements
- The automation shall complete within acceptable time bounds
- The system shall be idempotent where possible to allow safe re-execution
- All configuration shall be externalized (not hardcoded)
- The implementation shall follow the patterns defined in brain/patterns.md

## Scope

**In Scope:**
- Implementation of the core automation logic for "{title}"
- Error handling and logging
- Configuration management
- Basic monitoring and alerting

**Out of Scope:**
- UI or dashboard development (handled by Kanban UI phase)
- Integration with external notification systems (handled by Telegram phase)
- Long-term data retention and archival
- Multi-environment deployment automation

## Edge Cases

- **Empty or invalid input**: The system shall validate all inputs before processing
- **Network failures**: The automation shall retry with exponential backoff on transient failures
- **Concurrent execution**: The system shall prevent duplicate concurrent runs of the same automation
- **Partial completion**: If the automation fails mid-way, it shall clean up any partial state
- **Permission denied**: The system shall log and alert on permission errors without crashing
- **Resource exhaustion**: The automation shall monitor and respect resource limits (disk, memory, API quotas)

## Constraints

- All secrets and credentials must be read from environment variables or a secure vault — never hardcoded
- The automation must not modify production data without explicit approval
- All changes must be reversible or have a rollback plan
- The implementation must be compatible with the existing Python agent framework
- Maximum execution time should be bounded and configurable

## PII / Secret Handling Notes

- No PII (Personally Identifiable Information) is expected to be handled by this automation
- Any credentials required shall be sourced from environment variables using `os.getenv()`
- Secrets must never be logged, printed, or written to files
- If the automation interacts with external APIs, tokens shall be passed via secure headers
- Review brain/patterns.md for organization-specific secret management conventions

## Dependencies

- Python 3.8+ runtime
- Access to the systems being automated
- Required Python packages as specified in requirements.txt
- Network access for any external API calls
- Appropriate IAM permissions / service account access
{patterns_section}"""


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

    Scoring criteria:
    - Length >= 500 chars: 40 points, >= 200 chars: 20 points, else 0
    - Has sections: requirements, scope, edge cases, constraints, pii/secret: 30 points (6 each)
    - References patterns: 20 points
    - Has specific/actionable content (bullet points or numbered lists): 10 points

    Args:
        spec_content (str): The spec document content.

    Returns:
        int: Confidence score between 0 and 100.
    """
    score = 0
    content_lower = spec_content.lower()

    # Length scoring (40 points max)
    if len(spec_content) >= 500:
        score += 40
    elif len(spec_content) >= 200:
        score += 20

    # Section coverage scoring (30 points max, 6 each)
    sections = ["requirements", "scope", "edge cases", "constraints", "pii"]
    for section in sections:
        if section in content_lower:
            score += 6

    # Patterns reference scoring (20 points)
    if "pattern" in content_lower:
        score += 20

    # Specific/actionable content scoring (10 points)
    if re.search(r'[-*]\s', spec_content) or re.search(r'\d+\.\s', spec_content):
        score += 10

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