"""P3.2.3 — planner must fail loud, not silently substitute a stub checklist.

When the planner LLM returns empty / unparseable output, ``create_checklist``
now returns ``[]`` (NOT the old 3-task stub), and ``ExecutorAgent.execute``
aborts on the empty plan so :func:`executor_idea` returns ``0`` with a
FAILURE ``execution_report.md`` and **no** ``COMPLETED:`` log entries.

This test stubs the planner's LLM (no live ``bob`` / network) and drives the
real 3-arg ``executor_idea(item_id, run_manager, run_id)`` signature against
a synthetic requirement tree under ``tmp_path``.
"""
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


def _install_mock_llm(monkeypatch, chat_return: str):
    """Install a mock ``agents.llm_client.LLMClient`` in sys.modules.

    The planner calls ``self.llm.chat(...)`` once; we drive it via
    ``chat_return`` (empty string or non-JSON).  Restored by monkeypatch
    teardown.
    """
    mock_mod = ModuleType("agents.llm_client")
    mock_client = MagicMock()
    mock_client.chat.return_value = chat_return
    mock_mod.LLMClient = MagicMock(return_value=mock_client)
    monkeypatch.setitem(sys.modules, "agents.llm_client", mock_mod)
    return mock_client


def _build_requirement_tree(root: str, item_id: str) -> str:
    """Create a minimal config.yaml + spec.md + architecture.md under root."""
    with open(os.path.join(root, "config.yaml"), "w") as f:
        f.write("llm:\n  provider: mock\n  model: mock\n")
    req_dir = os.path.join(root, "automation-ideas", "requirements", item_id)
    os.makedirs(req_dir, exist_ok=True)
    with open(os.path.join(req_dir, "spec.md"), "w") as f:
        f.write("# Spec\n\n## Overview\nA simple idea.\n")
    with open(os.path.join(req_dir, "architecture.md"), "w") as f:
        f.write("# Arch\n\n## Tech Stack Decisions\n- Python\n")
    return req_dir


def _run_executor_idea(tmp_path, monkeypatch, item_id: str, chat_return: str):
    monkeypatch.chdir(tmp_path)
    req_dir = _build_requirement_tree(str(tmp_path), item_id)
    mock_client = _install_mock_llm(monkeypatch, chat_return)
    from agents.executor import executor_idea  # imports mocked LLMClient

    run_manager = MagicMock()
    run_manager.log_event.return_value = True
    result = executor_idea(item_id, run_manager, run_id=f"run-{item_id}")
    return result, req_dir, mock_client


def test_empty_planner_response_returns_zero_and_failure_report(
    monkeypatch, tmp_path
):
    result, req_dir, mock_client = _run_executor_idea(
        tmp_path, monkeypatch, "TEST-P323-001", chat_return=""
    )

    # Acceptance: confidence 0 (executor_idea returns 100 on success, 0 on fail)
    assert result == 0, f"expected 0 (failure), got {result}"

    # Acceptance: a FAILURE report was written, with NO COMPLETED: entries.
    report_path = os.path.join(req_dir, "execution_report.md")
    assert os.path.exists(report_path), "execution_report.md was not written"
    report = open(report_path).read()
    assert "FAILURE" in report, f"report is not a FAILURE report:\n{report}"
    assert "COMPLETED:" not in report, (
        f"FAILURE report must contain no COMPLETED log entries:\n{report}"
    )

    # Planner was actually consulted (proves the empty path, not a skip)
    assert mock_client.chat.call_count >= 1, "planner LLM was never called"


def test_unparseable_planner_json_also_fails_loud(monkeypatch, tmp_path):
    """A non-JSON planner response (not just empty string) must also fail loud."""
    result, req_dir, _ = _run_executor_idea(
        tmp_path, monkeypatch, "TEST-P323-002",
        chat_return="sorry, I cannot help with that",
    )
    assert result == 0, f"expected 0 (failure), got {result}"
    report_path = os.path.join(req_dir, "execution_report.md")
    assert os.path.exists(report_path)
    report = open(report_path).read()
    assert "FAILURE" in report
    assert "COMPLETED:" not in report


def test_create_checklist_returns_empty_list_on_empty_response():
    """Direct unit test of the planner: empty LLM output -> [] (not a 3-task
    stub).  Guards the removal of the placeholder checklist directly."""
    from agents.executor_planner import ExecutorPlanner

    planner = ExecutorPlanner.__new__(ExecutorPlanner)  # bypass __init__ LLMClient
    planner.llm = MagicMock()
    planner.llm.chat.return_value = ""

    result = planner.create_checklist("spec", "arch")
    assert result == [], f"expected [], got {result!r}"
    # Explicitly NOT the old stub tasks:
    assert not any("Initialize workspace" == t.get("task") for t in result)
    assert not any("Implement core logic" == t.get("task") for t in result)
    assert not any("Run verification tests" == t.get("task") for t in result)
