"""Live-LLM check of the tester agent (deselected by default).

Run with: pytest -m live_llm tests/test_tester_integration.py
Needs GOOGLE_API_KEY_KANBAN and network. Writes only under the per-test tmp
data dir provided by the autouse ``isolate_data_dir`` fixture. Offline coverage
of the same function lives in tests/test_tester.py.
"""
import os

import pytest

# Deliberately does NOT load the project .env: a live test runs only when the
# caller exports GOOGLE_API_KEY_KANBAN explicitly (opt-in via -m live_llm).
pytestmark = pytest.mark.live_llm

SPEC = (
    "# Spec\n\n## Overview\nTest spec.\n\n## Requirements\n- Req 1\n\n"
    "## Scope\n- Scope 1\n\n## Edge Cases\n- Edge 1\n\n## Constraints\n- Const 1\n\n"
    "## PII / Secret Handling Notes\n- None"
)
ARCH = (
    "# Arch\n\n## Architecture Diagram\n```mermaid\ngraph TD\nA --> B\n```\n\n"
    "## Tech Stack Decisions\n- Python\n\n## Risk Flags\n- Low\n\n"
    "## Dry-Run Notes\n- None\n\n## Constraints and Assumptions\n- None"
)


def test_tester_integration(isolate_data_dir, monkeypatch):
    if not os.getenv("GOOGLE_API_KEY_KANBAN"):
        pytest.skip("GOOGLE_API_KEY_KANBAN not set")

    import agents.tester as tester
    from agents.llm_client import LLMClient

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = LLMClient(config_path=os.path.join(root, "config.yaml"))
    client.model = "gemma-4-26b-a4b-it"
    monkeypatch.setattr(tester, "llm", client)

    test_id = "TEST-TEST-001"
    req_dir = isolate_data_dir / "requirements" / test_id
    req_dir.mkdir(parents=True)
    (req_dir / "spec.md").write_text(SPEC)
    (req_dir / "architecture.md").write_text(ARCH)

    confidence = tester.tester_idea(test_id)

    tests_path = req_dir / "tests.md"
    assert tests_path.is_file(), "tests.md was not written"
    content = tests_path.read_text()
    assert not LLMClient.is_stub(content), "LLM returned a stub response"
    lowered = content.lower()
    assert "given" in lowered and "when" in lowered and "then" in lowered
    assert isinstance(confidence, int) and confidence > 0
