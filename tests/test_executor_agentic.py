"""Executor Agent mocked-LLM logic test.

Historically this module mocked ``agents.llm_client`` by injecting a fake
module into ``sys.modules`` at *import* time and mocking
``antikythera_tools``.  Both mocks leaked for the rest of the pytest session:
the late-undo ``pytest_runtest_teardown`` hook in ``conftest.py`` restored
``agents.llm_client`` only *after* this test executed, so any test that ran
before this one (alphabetic ordering) and did ``from agents.llm_client
import LLMClient`` received the ``MagicMock`` and blew up on
``LLMClient.__new__(LLMClient)`` (``issubclass() arg 1 must be a class``) —
notably ``tests/test_bob_stub_seam.py``.

Now we follow the same modern pattern as ``tests/test_executor_planner_fail_loud.py``:
patch only the *bound name* ``LLMClient`` in ``agents.executor`` (and
``agents.executor_planner``) via ``monkeypatch`` (scoped to the test,
auto-undone), write a synthetic ``config.yaml`` + spec/arch under
``tmp_path``, and call the current 3-arg ``executor_idea(item_id, run_manager,
run_id)`` signature.  ``antikythera_tools`` no longer exists in the codebase
(the executor reaches tools through ``agents.executor_tools``), so that mock
is dropped entirely.
"""
import os
import sys
from unittest.mock import MagicMock

# Ensure the repo root is importable for `agents.*` / `api.*`.
sys.path.append(os.getcwd())


def _install_mock_llm(monkeypatch, chat_side_effect):
    """Install a mock ``LLMClient`` the executor + planner will actually use.

    ``executor_idea`` constructs ``LLMClient(config_path=...)`` fresh, so we
    patch the *bound name* in both consumer modules — not just ``sys.modules``
    — otherwise an already-imported ``agents.llm_client`` would shadow the
    mock and the test would become order-dependent.  Restored by monkeypatch
    teardown (no session-wide pollution).
    """
    mock_client = MagicMock()
    mock_client.chat.side_effect = chat_side_effect
    mock_llm_cls = MagicMock(return_value=mock_client)

    import agents.executor as exec_mod
    import agents.executor_planner as planner_mod
    monkeypatch.setattr(exec_mod, "LLMClient", mock_llm_cls, raising=False)
    monkeypatch.setattr(planner_mod, "LLMClient", mock_llm_cls, raising=False)
    return mock_client


def _build_requirement_tree(root, item_id):
    """Create a minimal config.yaml + spec.md + architecture.md under root."""
    with open(os.path.join(root, "config.yaml"), "w") as f:
        f.write("llm:\n  provider: mock\n  model: mock\n")
    req_dir = os.path.join(root, "automation-ideas", "requirements", item_id)
    os.makedirs(req_dir, exist_ok=True)
    with open(os.path.join(req_dir, "spec.md"), "w") as f:
        f.write(
            "# Spec\n\n## Overview\nTest spec.\n\n## Requirements\n- Req 1\n\n"
            "## Scope\n- Scope 1\n\n## Edge Cases\n- Edge 1\n\n## Constraints\n"
            "- Const 1\n\n## PII / Secret Handling Notes\n- None"
        )
    with open(os.path.join(req_dir, "architecture.md"), "w") as f:
        f.write(
            "# Arch\n\n## Architecture Diagram\n```mermaid\ngraph TD\nA --> B\n"
            "```\n\n## Tech Stack Decisions\n- Python\n\n## Risk Flags\n- Low\n"
            "\n## Dry-Run Notes\n- None\n\n## Constraints and Assumptions\n- None"
        )
    return req_dir


def test_executor_agentic_mocked(monkeypatch, tmp_path):
    print("--- Executor Agent Mocked Logic Test ---")

    monkeypatch.chdir(tmp_path)
    item_id = "TEST-MOCK-001"
    req_dir = _build_requirement_tree(str(tmp_path), item_id)

    # Planner call returns a one-task checklist; executor call returns a
    # write_file tool call landing a real artifact under requirements/<id>/.
    chat_side_effect = [
        '[{"task": "test task", "type": "file_creation"}]',  # Planner
        '{"tool": "write_file", "args": {"path": "test_file.txt", "content": "hello"}}',  # Executor
    ]
    mock_client = _install_mock_llm(monkeypatch, chat_side_effect)

    run_manager = MagicMock()
    run_manager.log_event.return_value = True

    try:
        print(f"Running executor_idea for {item_id}...")
        from agents.executor import executor_idea
        result = executor_idea(item_id, run_manager, run_id=f"run-{item_id}")

        assert result == 100, f"executor_idea returned {result}, expected 100"
        print("SUCCESS: executor_idea returned 100.")

        # The executor should have actually driven the mocked LLM (planner +
        # exactly one executor turn in the happy path — total 2 calls).
        assert mock_client.chat.call_count == 2, (
            f"expected 2 LLM calls (planner + executor), "
            f"got {mock_client.chat.call_count}"
        )
    finally:
        print(f"Chat call count: {mock_client.chat.call_count}")


if __name__ == "__main__":
    # Manual-run shim: pytest provides monkeypatch/tmp_path, so fall back to
    # unittest.mock.patch context managers for the same scoped mocking.
    import tempfile
    from unittest.mock import patch
    import agents.executor as exec_mod
    import agents.executor_planner as planner_mod

    with tempfile.TemporaryDirectory() as td:
        os.chdir(td)
        item_id = "TEST-MOCK-001"
        _build_requirement_tree(td, item_id)
        mock_client = MagicMock()
        mock_client.chat.side_effect = [
            '[{"task": "test task", "type": "file_creation"}]',
            '{"tool": "write_file", "args": {"path": "test_file.txt", "content": "hello"}}',
        ]
        mock_cls = MagicMock(return_value=mock_client)
        with patch.object(exec_mod, "LLMClient", mock_cls, raising=False), \
             patch.object(planner_mod, "LLMClient", mock_cls, raising=False):
            from agents.executor import executor_idea
            rm = MagicMock()
            rm.log_event.return_value = True
            success = executor_idea(item_id, rm, run_id=f"run-{item_id}") == 100
    sys.exit(0 if success else 1)
