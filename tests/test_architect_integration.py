"""Live-LLM check of the architect agent (deselected by default).

Run with: pytest -m live_llm tests/test_architect_integration.py
Needs GOOGLE_API_KEY_KANBAN and network. Writes only under the per-test tmp
data dir provided by the autouse ``isolate_data_dir`` fixture. Offline coverage
of the same function lives in tests/test_architect.py.
"""
import os

import pytest

# Deliberately does NOT load the project .env: a live test runs only when the
# caller exports GOOGLE_API_KEY_KANBAN explicitly (opt-in via -m live_llm).
pytestmark = pytest.mark.live_llm

SPEC = """# Specification for {id}: Test Architecture Idea

## Overview
This is a test specification to verify the Architect Agent.

## Requirements
- Requirement 1
- Requirement 2

## Scope
- In scope: testing the architect.
- Out of scope: production deployment.

## Edge Cases
- Invalid input.

## Constraints
- Must be AI generated.

## PII / Secret Handling Notes
- No PII.
"""


def test_architect_integration(isolate_data_dir, monkeypatch):
    if not os.getenv("GOOGLE_API_KEY_KANBAN"):
        pytest.skip("GOOGLE_API_KEY_KANBAN not set")

    import agents.architect as architect
    from agents.llm_client import LLMClient

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = LLMClient(config_path=os.path.join(root, "config.yaml"))
    client.model = "gemma-4-26b-a4b-it"
    monkeypatch.setattr(architect, "llm", client)

    test_id = "TEST-ARCH-001"
    req_dir = isolate_data_dir / "requirements" / test_id
    req_dir.mkdir(parents=True)
    (req_dir / "spec.md").write_text(SPEC.format(id=test_id))

    confidence = architect.architect_idea(test_id)

    arch_path = req_dir / "architecture.md"
    assert arch_path.is_file(), "architecture.md was not written"
    content = arch_path.read_text()
    assert not LLMClient.is_stub(content), "LLM returned a stub response"
    assert "mermaid" in content.lower() or "graph TD" in content
    assert isinstance(confidence, int) and confidence > 0
