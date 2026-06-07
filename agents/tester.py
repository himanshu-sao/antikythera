"""
Tester Agent — reads architecture.md + spec.md and writes tests.md using an LLM.

The Tester generates comprehensive test plans with test cases,
validation checklists, expected outputs, and edge case coverage.
"""

import os
import logging
from agents.llm_client import LLMClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")

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


def _extract_title(content):
    """
    Extract the title from content (first # heading).
    """
    import re
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled"


def write_tests(idea_id, test_content):
    """
    Write test content to requirements/ID-XXX/tests.md.
    """
    dir_path = os.path.join(REQUIREMENTS_DIR, idea_id)
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "tests.md")
    with open(file_path, "w") as f:
        f.write(test_content)
    return file_path


def calculate_confidence(test_content):
    """
    Calculate a confidence score (0-100) for a test plan document.
    Heuristic check for required sections.
    """
    score = 0
    content_lower = test_content.lower()
    
    # Section check
    sections = ["test plan", "test case", "validation checklist", "expected output", "edge case"]
    for section in sections:
        if section in content_lower:
            score += 20
            
    return min(score, 100)


def provision_docker_sandbox():
    """
    Provision a Docker sandbox for running tests.
    """
    import subprocess
    compose_file = os.path.join(DOCKER_DIR, "docker-compose.yml")
    if not os.path.exists(compose_file):
        logger.warning("Docker Compose file not found at %s", compose_file)
        return False

    try:
        result = subprocess.run(
            ["docker-compose", "-f", compose_file, "up", "-d"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Docker sandbox provisioned successfully")
            return True
        else:
            logger.warning("Docker sandbox provisioning failed: %s", result.stderr.strip())
            return False
    except Exception as e:
        logger.warning("Docker sandbox provisioning error: %s", str(e))
        return False


def tester_idea(idea_id, use_docker=False):
    """
    Generate a test plan document for a pipeline item using an LLM.

    Reads requirements/ID-XXX/spec.md and requirements/ID-XXX/architecture.md,
    generates a comprehensive test plan, writes it to
    requirements/ID-XXX/tests.md, and returns a confidence score.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        use_docker (bool): Whether to provision a Docker sandbox.

    Returns:
        int: Confidence score (0-100).

    Raises:
        FileNotFoundError: If spec.md or architecture.md does not exist.
        ValueError: If spec or architecture content is empty.
    """
    spec_path = os.path.join(REQUIREMENTS_DIR, idea_id, "spec.md")
    arch_path = os.path.join(REQUIREMENTS_DIR, idea_id, "architecture.md")
    
    if not os.path.exists(spec_path):
        raise FileNotFoundError(f"Spec file not found: {spec_path}")
    if not os.path.exists(arch_path):
        raise FileNotFoundError(f"Arch file not found: {arch_path}")
        
    spec_content = _read_file(spec_path)
    arch_content = _read_file(arch_path)

    if not spec_content or not spec_content.strip():
        raise ValueError("Spec content is empty")
    if not arch_content or not arch_content.strip():
        raise ValueError("Architecture content is empty")

    if use_docker:
        sandbox_ok = provision_docker_sandbox()
        if not sandbox_ok:
            logger.warning("Continuing without Docker sandbox.")

    logger.info("Testing idea %s...", idea_id)

    system_prompt = """You are the Antikythera Tester Agent. Your goal is to transform a technical specification and architecture into a professional and actionable test plan.

Your output must be in valid Markdown format.

Follow these guidelines:
1. **Proportionality**: Scale the test coverage to the actual risk and complexity of the tool. A simple script needs a few targeted tests; a complex system needs a full suite.
2. **Strict Adherence**: Do NOT create "filler" tests or invent scenarios that are outside the scope of the specification.
3. **Structure**: Use these headings as a guide, but omit categories that are not applicable:
   # Test Plan for [ID]: [Title]
   ## Test Plan Overview
   ## Test Cases
   ### Unit Tests
   ### Integration Tests
   ### End-to-End Tests
   ## Validation Checklist
   ## Expected Outputs
   ## Edge Cases Covered
4. **Content**: Create realistic test scenarios. 
   - Use "Given/When/Then" format for test cases to ensure clarity.
5. **Coverage**: Address security, error handling, and edge cases identified in the spec and architecture, scaled to the tool's complexity.

Your response should ONLY contain the markdown content for the test plan document."""

    user_prompt = f"Based on the following Specification and Architecture, generate a comprehensive test plan:\n\n### SPECIFICATION:\n{spec_content}\n\n### ARCHITECTURE:\n{arch_content}"

    try:
        test_content = llm.generate_structured_content(system_prompt, user_prompt)
        write_tests(idea_id, test_content)
        confidence = calculate_confidence(test_content)
        logger.info("Tester completed for %s with confidence %d", idea_id, confidence)
        return confidence
    except Exception as e:
        logger.error("Tester failed for %s: %s", idea_id, str(e))
        raise e
