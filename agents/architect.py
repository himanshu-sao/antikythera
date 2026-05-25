"""
Architect Agent — reads spec.md and writes architecture.md using an LLM.

The Architect generates comprehensive architecture documents with
Mermaid diagrams, tech stack decisions, risk flags, dry-run notes,
and constraints/assumptions.
"""

import os
import logging
from typing import Optional
from agents.llm_client import LLMClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
BRAIN_PATTERNS = os.path.join(PROJECT_ROOT, "automation-ideas", "brain", "patterns.md")

logger = logging.getLogger(__name__)

# Initialize LLM Client using central config
llm = LLMClient(config_path=os.path.join(PROJECT_ROOT, "config.yaml"))

def _read_file(file_path):
    """
    Read the contents of a file.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r") as f:
        return f.read()


def _read_patterns(patterns_path=None):
    """
    Read patterns from brain/patterns.md.
    """
    path = patterns_path or BRAIN_PATTERNS
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return None


def _extract_title(spec_content):
    """
    Extract the title from spec content (first # heading).
    """
    import re
    match = re.search(r'^#\s+(.+)$', spec_content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled"


def write_architecture(idea_id, architecture_content):
    """
    Write architecture content to requirements/ID-XXX/architecture.md.
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
    Heuristic check for required sections.
    """
    score = 0
    content_lower = architecture_content.lower()
    
    # Section check
    sections = ["architecture diagram", "tech stack", "risk flag", "dry-run", "constraint"]
    for section in sections:
        if section in content_lower:
            score += 20
            
    return min(score, 100)


def _generate_architecture_content(idea_id: str, spec_content: str, patterns_content: Optional[str] = None) -> str:
    """
    Internal method to generate the markdown content for the architecture.
    This is used by tests and can be exposed if needed.
    """
    system_prompt = f"""You are the Antikythera Architect Agent. Your goal is to transform a technical specification into a professional technical architecture document.

Your output must be in valid Markdown format.

Follow these guidelines:
1. **Proportionality**: Scale the technical depth to the complexity of the specification. A simple utility needs a simple architecture; a complex system needs a detailed one.
2. **Strict Adherence**: Do NOT invent new infrastructure, add unrelated components, or change the core intent of the specification.
3. **Structure**: Use these headings as a guide, but omit those that are not applicable to the specific task:
   # Architecture for [ID]: [Title]
   ## Architecture Diagram (Include a Mermaid graph TD diagram)
   ## Tech Stack Decisions
   ## Risk Flags (Low/Medium/High)
   ## Dry-Run Notes
   ## Constraints and Assumptions
4. **Diagrams**: Always include a `mermaid` code block with a `graph TD` diagram that visually represents the data flow or component interaction.
5. **Detail**: Be specific about technology choices and error handling only where it adds real value.
6. **Patterns**: Incorporate the following patterns from the system's brain:
{patterns_content if patterns_content else "No specific patterns provided."}

Your response should ONLY contain the markdown content for the architecture document."""

    user_prompt = f"Based on this specification, design a technical architecture:\n\n{spec_content}"

    architecture_content = llm.generate_structured_content(system_prompt, user_prompt)
    
    if patterns_content:
        architecture_content += f"\n\n## Patterns Referenced\n{patterns_content}"
        
    return architecture_content


def architect_idea(idea_id, patterns_path=None):
    """
    Generate an architecture document for a pipeline item using an LLM.

    Reads requirements/ID-XXX/spec.md and brain/patterns.md for context,
    generates a comprehensive architecture document, writes it to
    requirements/ID-XXX/architecture.md, and returns a confidence score.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        patterns_path (str, optional): Path to patterns.md.

    Returns:
        int: Confidence score (0-100).

    Raises:
        FileNotFoundError: If spec.md does not exist.
        ValueError: If spec content is empty.
    """
    spec_path = os.path.join(REQUIREMENTS_DIR, idea_id, "spec.md")
    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
        
    spec_content = _read_file(spec_path)

    if not spec_content or not spec_content.strip():
        raise ValueError("Spec content is empty")

    patterns_content = _read_patterns(patterns_path)
    title = _extract_title(spec_content)

    logger.info("Architecting idea %s: %s", idea_id, title)

    try:
        architecture_content = _generate_architecture_content(idea_id, spec_content, patterns_content)
        write_architecture(idea_id, architecture_content)
        confidence = calculate_confidence(architecture_content)
        logger.info("Architect completed for %s with confidence %d", idea_id, confidence)
        return confidence
    except Exception as e:
        logger.error("Architect failed for %s: %s", idea_id, str(e))
        raise e
