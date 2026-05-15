"""
Tester Agent — reads architecture.md + spec.md and writes tests.md.

The Tester generates comprehensive test plans with test cases,
validation checklists, expected outputs, and edge case coverage.
Optionally provisions a Docker sandbox for running tests.
"""

import os
import re
import subprocess
import logging

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIREMENTS_DIR = os.path.join(PROJECT_ROOT, "automation-ideas", "requirements")
DOCKER_DIR = os.path.join(PROJECT_ROOT, "docker")


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


def _extract_title(content):
    """
    Extract the title from content (first # heading).

    Args:
        content (str): The document content.

    Returns:
        str: The extracted title, or "Untitled" if not found.
    """
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled"


def _generate_test_plan_content(idea_id, spec_content, architecture_content):
    """
    Generate a comprehensive test plan document.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        spec_content (str): The spec document content.
        architecture_content (str): The architecture document content.

    Returns:
        str: The generated test plan markdown content.
    """
    title = _extract_title(spec_content)

    return f"""# Test Plan for {idea_id}: {title}

## Test Plan Overview

This test plan covers the implementation of {title}. It includes unit tests,
integration tests, and end-to-end validation to ensure the automation works
correctly and handles edge cases gracefully.

## Test Cases

### Unit Tests

1. **TC-{idea_id}-001: Basic functionality**
   - **Given**: Standard input conditions
   - **When**: The automation is executed
   - **Then**: It should produce the expected output
   - **Type**: Unit

2. **TC-{idea_id}-002: Error handling**
   - **Given**: Invalid input or error condition
   - **When**: The automation encounters the error
   - **Then**: It should handle it gracefully and log the error
   - **Type**: Unit

### Integration Tests

1. **TC-{idea_id}-003: End-to-end flow**
   - **Given**: All components are available
   - **When**: The full pipeline is executed
   - **Then**: All stages complete successfully
   - **Type**: Integration

### End-to-End Tests

1. **TC-{idea_id}-004: Full pipeline validation**
   - **Given**: A complete set of inputs
   - **When**: The automation runs from start to finish
   - **Then**: The output matches expected results
   - **Type**: E2E

## Validation Checklist

- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Error handling works correctly
- [ ] Edge cases are covered
- [ ] No secrets or PII exposed in logs
- [ ] Idempotency verified

## Expected Outputs

- Successful execution returns exit code 0
- All actions are logged with timestamps
- Output files are written to the correct locations
- Errors are logged without crashing the process

## Edge Cases Covered

- **Empty input**: Validated before processing
- **Network failure**: Retry with backoff
- **Concurrent execution**: Prevented with locking
- **Partial failure**: Clean up partial state
- **Permission denied**: Logged without crash
- **Resource exhaustion**: Monitored and bounded
"""


def write_tests(idea_id, test_content):
    """
    Write test content to requirements/ID-XXX/tests.md.

    Args:
        idea_id (str): The item ID (e.g. "ID-001").
        test_content (str): The markdown content to write.

    Returns:
        str: The path to the written file.
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

    Scoring criteria:
    - Length >= 300 chars: 30 points, >= 100 chars: 15 points, else 0
    - Has sections: test plan, test cases, validation checklist, expected outputs, edge cases: 40 points (8 each)
    - Has specific test scenarios (Given/When/Then): 15 points
    - Has specific/actionable content (bullet points or numbered lists): 15 points

    Args:
        test_content (str): The test plan document content.

    Returns:
        int: Confidence score between 0 and 100.
    """
    score = 0
    content_lower = test_content.lower()

    # Length scoring (30 points max)
    if len(test_content) >= 300:
        score += 30
    elif len(test_content) >= 100:
        score += 15

    # Section coverage scoring (40 points max, 8 each)
    sections = ["test plan", "test case", "validation checklist", "expected output", "edge case"]
    for section in sections:
        if section in content_lower:
            score += 8

    # Specific test scenarios scoring (15 points)
    if "given" in content_lower and "when" in content_lower and "then" in content_lower:
        score += 15

    # Specific/actionable content scoring (15 points)
    if re.search(r'[-*]\s', test_content) or re.search(r'\d+\.\s', test_content):
        score += 15

    return min(score, 100)


def provision_docker_sandbox():
    """
    Provision a Docker sandbox for running tests.

    Uses Docker Compose to start a sandbox container defined in
    docker/docker-compose.yml. Returns False gracefully if Docker
    is not available or provisioning fails.

    Returns:
        bool: True if sandbox was provisioned successfully, False otherwise.
    """
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
            logger.warning(
                "Docker sandbox provisioning failed: %s",
                result.stderr.strip(),
            )
            return False
    except FileNotFoundError:
        logger.warning("Docker not available on this system")
        return False
    except subprocess.TimeoutExpired:
        logger.warning("Docker sandbox provisioning timed out")
        return False
    except Exception as e:
        logger.warning("Docker sandbox provisioning error: %s", str(e))
        return False


def tester_idea(idea_id, use_docker=False):
    """
    Generate a test plan document for a pipeline item.

    Reads requirements/ID-XXX/spec.md and requirements/ID-XXX/architecture.md,
    generates a comprehensive test plan, writes it to
    requirements/ID-XXX/tests.md, and returns a confidence score.

    Optionally provisions a Docker sandbox if use_docker is True.

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

    spec_content = _read_file(spec_path)
    arch_content = _read_file(arch_path)

    if not spec_content or not spec_content.strip():
        raise ValueError("Spec content is empty")
    if not arch_content or not arch_content.strip():
        raise ValueError("Architecture content is empty")

    if use_docker:
        sandbox_ok = provision_docker_sandbox()
        if sandbox_ok:
            logger.info("Docker sandbox provisioned for %s", idea_id)
        else:
            logger.warning(
                "Continuing without Docker sandbox for %s", idea_id
            )

    test_content = _generate_test_plan_content(idea_id, spec_content, arch_content)
    write_tests(idea_id, test_content)
    confidence = calculate_confidence(test_content)

    logger.info(
        "Tester completed for %s with confidence %d",
        idea_id,
        confidence,
    )
    return confidence