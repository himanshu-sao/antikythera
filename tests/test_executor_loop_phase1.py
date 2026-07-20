"""P3.2.6 Phase 1 — ``ExecutorAgent._perform_task_multi_turn`` loop behaviour.

Phase 1 removed the per-task OUTER retry layer that wrapped the inner
multi-turn loop.  Before Phase 1 a stuck task cost 4 × 5 = 20 LLM turns
(inner 5-turn loop × outer 3-wide retry) before a hard ``raise`` aborted the
run.  Now there is a single bounded loop of ``MAX_TASK_ATTEMPTS`` turns and
no outer retry.

These tests pin the two correctness properties of the simplified loop and
guard the live-bug fix directly:

* ``test_terminal_only_task_exhausts_max_attempts_not_20`` — a task whose
  LLM only ever emits ``terminal`` (e.g. ``ls``) must loop exactly
  ``MAX_TASK_ATTEMPTS`` times, then return ``False``.  It must NOT return
  ``True`` (old false-green on a recognised command) and must NOT invoke the
  LLM 20 times (old 4×5 outer-retry burn).

* ``test_write_file_task_completes_in_one_turn`` — a task whose LLM emits a
  valid ``write_file`` of non-stub content completes in a single turn.

The LLM is stubbed via a side_effect list so we can count the exact number of
``chat`` invocations.  ``RunManager`` is a MagicMock (``log_event`` no-op).
"""
import os
import json
from unittest.mock import MagicMock

import pytest


def _tool_call(tool: str, **args) -> str:
    """Build a valid executor tool-call JSON response (escaped properly)."""
    return json.dumps({"tool": tool, "args": args})


_REAL_CONTENT = (
    "def health():\n"
    "    return {'status': 'ok'}\n"
    "# a real, complete handler body\n"
)


def _make_executor(monkeypatch, chat_side_effect):
    """Build a real ``ExecutorAgent`` with a stubbed LLMClient.

    The executor constructs ``LLMClient(config_path=...)`` itself, so we patch
    the bound name in ``agents.executor`` (mirroring the fail-loud test's
    approach) to return a MagicMock whose ``chat`` has the given side_effect.
    ``MAX_TASK_ATTEMPTS`` is taken from the real attribute so the test follows
    the constant rather than hard-coding 5.
    """
    import agents.executor as exec_mod

    mock_client = MagicMock()
    mock_client.chat.side_effect = chat_side_effect
    mock_llm_cls = MagicMock(return_value=mock_client)
    monkeypatch.setattr(exec_mod, "LLMClient", mock_llm_cls, raising=False)

    run_manager = MagicMock()
    run_manager.log_event.return_value = True
    executor = exec_mod.ExecutorAgent(
        config_path=os.devnull, run_manager=run_manager, run_id="run-loop-test"
    )
    return executor, mock_client


def test_terminal_only_task_exhausts_max_attempts_not_20(monkeypatch, tmp_path):
    """A ``terminal``/``ls``-only task must NOT false-complete, and must NOT
    burn 4x5 turns.  ``terminal`` is never ``is_done`` (Phase 1), so the loop
    exhausts exactly ``MAX_TASK_ATTEMPTS`` LLM calls and returns False."""
    monkeypatch.chdir(tmp_path)

    ls_response = _tool_call("terminal", command="ls -la")
    many_ls = [ls_response] * 50

    executor, mock_client = _make_executor(monkeypatch, many_ls)
    max_attempts = executor.MAX_TASK_ATTEMPTS

    task = {"task": "verify files exist", "type": "verification"}
    done = executor._perform_task_multi_turn(task, "TEST-LOOP-001")

    assert done is False, "terminal-only task false-completed (Phase 1 regression)"
    assert mock_client.chat.call_count == max_attempts, (
        f"expected exactly {max_attempts} LLM calls (single bounded loop), "
        f"got {mock_client.chat.call_count} (outer-retry layer regressed?)"
    )
    assert mock_client.chat.call_count < 20, (
        "outer retry layer reintroduced: burned >=20 turns on one stuck task"
    )


def test_write_file_task_completes_in_one_turn(monkeypatch, tmp_path):
    """A ``write_file`` of real content completes in a single LLM turn.

    Per the P3.2.7 follow-up, ``execute_tool`` anchors a RELATIVE tool path at
    ``automation-ideas/requirements/<item_id>/`` (not cwd), so the artifact
    lands at ``<cwd>/automation-ideas/requirements/<item_id>/<target>`` —
    ``tmp_path`` here is cwd via ``monkeypatch.chdir``.
    """
    monkeypatch.chdir(tmp_path)
    target = os.path.join("api", "health_router.py")
    write_resp = _tool_call("write_file", path=target, content=_REAL_CONTENT)

    executor, mock_client = _make_executor(
        monkeypatch, [write_resp, _tool_call("write_file", path="unused", content="x")]
    )

    item_id = "TEST-LOOP-002"
    task = {"task": "Create api/health_router.py with GET /health", "type": "file_creation"}
    done = executor._perform_task_multi_turn(task, item_id)

    abs_target = os.path.join(
        str(tmp_path), "automation-ideas", "requirements", item_id, target
    )
    assert done is True, "valid write_file did not complete the task"
    assert mock_client.chat.call_count == 1, (
        f"expected 1 LLM call for a one-shot write, got "
        f"{mock_client.chat.call_count}"
    )
    assert os.path.isfile(abs_target), "artifact was not actually written to disk"
    assert open(abs_target).read() == _REAL_CONTENT


def test_write_file_stub_content_does_not_complete(monkeypatch, tmp_path):
    """If the model writes stub content the task must NOT complete; the loop
    keeps going and the result is False (honest partial, no false-green)."""
    monkeypatch.chdir(tmp_path)
    target = os.path.join("stub.py")
    stub_resp = _tool_call("write_file", path=target, content="stub response")
    responses = [stub_resp] * 50

    executor, mock_client = _make_executor(monkeypatch, responses)
    max_attempts = executor.MAX_TASK_ATTEMPTS

    task = {"task": "Write the handler", "type": "code_implementation"}
    done = executor._perform_task_multi_turn(task, "TEST-LOOP-003")

    abs_target = os.path.join(str(tmp_path), target)
    assert done is False, "stub-content write false-completed (anti-stub regression)"
    assert mock_client.chat.call_count == max_attempts
    assert not os.path.isfile(abs_target), "stub content was written despite rejection"
