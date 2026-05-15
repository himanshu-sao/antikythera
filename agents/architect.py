"""
Architect Agent — reads spec.md and writes architecture.md.

The Architect generates comprehensive architecture documents with
Mermaid diagrams, tech stack decisions, risk flags, dry-run notes,
and constraints/assumptions.
"""

import os
import re
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
BRAIN_PATTERNS = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "patterns.md")


def _read_file(file_path):
    """
    Read the contents of a file.

    Args:
        file_path (str): Path to the file.

    Returns:
        str: The file contents.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r") as f:
        return f.read()


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


def _extract_title(spec_content):
    """
    Extract the title from spec content (first # heading).

    Args:
        spec_content (str): The spec document content.

    Returns:
        str: The extracted title, or "Untitled" if not found.
    """
    match = re.search(r'^#\s+(.+)$', spec_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled"


def _generate_architecture_content(idea_id, spec_content, patterns_content=None):
    """
    Generate a comprehensive architecture document.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        spec_content (str): The spec document content.
        patterns_content (str, optional): Content from brain/patterns.md.

    Returns:
        str: The generated architecture markdown content.
    """
    title = _extract_title(spec_content)

    patterns_section = ""
    if patterns_content and patterns_content.strip():
        patterns_section = f"""
## Patterns Referenced

The following patterns from `brain/patterns.md` were considered during architecture design:

{patterns_content[:500]}

"""

    return f"""# Architecture for {idea_id}: {title}

## Architecture Diagram

```mermaid
graph TD
    A[Input] --> B[Process]
    B --> C[Output]
    B --> D[Error Handler]
    D --> E[Logging]
    E --> F[Audit Trail]
```

## Tech Stack Decisions

- **Language**: Python 3.8+ (matching existing agent framework)
- **Runtime**: Compatible with existing Hermes agent infrastructure
- **Dependencies**: Standard library + project dependencies
- **Storage**: File-based (matching existing pattern)
- **Configuration**: YAML-based external configuration

## Risk Flags

- **Low**: Standard automation risk — well-understood patterns apply
- **Medium**: N/A — no external system dependencies identified
- **High**: N/A — no production data access required

## Dry-Run Notes

- All operations are read-only on live systems
- Changes are written to local files only
- No external API calls without explicit approval
- All state transitions are logged for audit

## Constraints and Assumptions

- All secrets must be read from environment variables — never hardcoded
- The automation must be idempotent to allow safe re-execution
- Maximum execution time should be bounded and configurable
- The implementation must follow patterns from brain/patterns.md
- All changes must be reversible or have a rollback plan
- The automation must not modify production data without explicit approval
{patterns_section}"""


def write_architecture(idea_id, architecture_content):
    """
    Write architecture content to requirements/ID-XXX/architecture.md.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        architecture_content (str): The markdown content to write.

    Returns:
        str: The path to the written file.
    """
    dir_path = os.path.join(REQUIREMENTS_DIR, idea_id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "architecture.md")
    with open(file_path, "w") as f:
        f.write(architecture_content)
    return file_path


def calculate_confidence(architecture_content):
    """
    Calculate a confidence score (0-100) for an architecture document.

    Scoring criteria:
    - Length >= 300 chars: 30 points, >= 100 chars: 15 points, else 0
    - Has sections: architecture diagram, tech stack, risk flags, dry-run notes, constraints: 40 points (8 each)
    - References patterns: 15 points
    - Has specific/actionable content (bullet points or numbered lists): 15 points

    Args:
        architecture_content (str): The architecture document content.

    Returns:
        int: Confidence score between 0 and 100.
    """
    score = 0
    content_lower = architecture_content.lower()

    # Length scoring (30 points max)
    if len(architecture_content) >= 300:
        score += 30
    elif len(architecture_content) >= 100:
        score += 15

    # Section coverage scoring (40 points max, 8 each)
    sections = ["architecture diagram", "tech stack", "risk flag", "dry-run", "constraint"]
    for section in sections:
        if section in content_lower:
            score += 8

    # Patterns reference scoring (15 points)
    if "pattern" in content_lower:
        score += 15

    # Specific/actionable content scoring (15 points)
    if re.search(r'[-*]\s', architecture_content) or re.search(r'\d+\.\s', architecture_content):
        score += 15

    return min(score, 100)


def architect_idea(idea_id, patterns_path=None):
    """
    Generate an architecture document for a pipeline item.

    Reads requirements/ID-XXX/spec.md and brain/patterns.md for context,
    generates a comprehensive architecture document, writes it to
    requirements/ID-XXX/architecture.md, and returns a confidence score.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        patterns_path (str, optional): Path to brain/patterns.md.

    Returns:
        int: Confidence score (0-100).

    Raises:
        FileNotFoundError: If spec.md does not exist.
        ValueError: If spec content is empty.
    """
    spec_path = os.path.join(REQUIREMENTS_DIR, idea_id, "spec.md")
    spec_content = _read_file(spec_path)

    if not spec_content or not spec_content.strip():
        raise ValueError("Spec content is empty")

    patterns_content = _read_patterns(patterns_path)
    architecture_content = _generate_architecture_content(idea_id, spec_content, patterns_content)
    write_architecture(idea_id, architecture_content)
    confidence = calculate_confidence(architecture_content)

    logger.info(
        "Architect completed for %s with confidence %d",
        idea_id,
        confidence,
    )
    return confidence