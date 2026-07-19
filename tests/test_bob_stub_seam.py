"""P3.2.4 — env-var seam that mocks only the ``ibm_bob`` (``bob`` CLI) call.

``LLMClient._chat_bob`` checks ``ANTIKYTHERA_BOB_STUB``: when truthy it returns
a deterministic response and never spawns the ``bob`` subprocess (saving bob
quota / avoiding the 8–15s per-call + hang behaviour).  Default = real ``bob``.

These tests target only the seam — no full suite, no real ``bob``, no network.
"""
import os
from unittest.mock import patch, MagicMock

import pytest


def _make_bob_client():
    """Build an LLMClient whose provider is ibm_bob, without a real config file.

    The real ``__init__`` would try to resolve a provider/model from
    ``AIEngineConfigService`` / ``config.yaml``.  For a seam unit test we bypass
    that and reach ``_chat_bob`` directly via __new__.
    """
    from agents.llm_client import LLMClient
    c = LLMClient.__new__(LLMClient)
    c.provider = "ibm_bob"
    c.model = ""   # no -m flag → bob picks its own default
    return c


def _lc_mod():
    from agents import llm_client as lc_mod
    return lc_mod


def test_bob_stub_on_returns_deterministic_and_no_subprocess(monkeypatch):
    """With ANTIKYTHERA_BOB_STUB truthy, _chat_bob returns a stub and never
    spawns the bob subprocess."""
    monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "1")
    lc_mod = _lc_mod()
    client = _make_bob_client()

    # If the seam ever falls through to the real path, this would explode
    # (bob binary not on PATH in CI / no auth).  Guard it explicitly:
    with patch.object(lc_mod.subprocess, "run") as fake_run:
        result = client._chat_bob("system", "user", 0.7)

    assert fake_run.call_count == 0, "stubbed bob must NOT spawn a subprocess"
    assert isinstance(result, str) and result, "stub must return a non-empty string"


def test_bob_stub_truthy_values(monkeypatch):
    """Each canonical truthy value enables the stub."""
    lc_mod = _lc_mod()
    for val in ("1", "true", "TRUE", "yes", "on", "anything"):
        monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", val)
        client = _make_bob_client()
        with patch.object(lc_mod.subprocess, "run") as fake_run:
            r = client._chat_bob("system", f"user-{val}", 0.7)
        assert fake_run.call_count == 0
        assert r and isinstance(r, str)


def test_bob_stub_off_falls_through_to_subprocess(monkeypatch):
    """With ANTIKYTHERA_BOB_STUB=0, the real path runs — we intercept
    subprocess.run so no real bob is spawned, and assert the command it
    would run is the real bob invocation (not the stub)."""
    monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "0")
    lc_mod = _lc_mod()
    client = _make_bob_client()

    fake_result = MagicMock()
    fake_result.returncode = 0
    fake_result.stdout = "bob-echo"
    fake_result.stderr = ""

    with patch.object(lc_mod.subprocess, "run", return_value=fake_result) as fake_run:
        out = client._chat_bob("system", "user", 0.7)

    assert fake_run.call_count == 1, "real bob path must spawn subprocess.run once"
    # the real command uses the bob binary and --chat-mode ask
    cmd = fake_run.call_args[0][0]
    assert isinstance(cmd, list)
    assert cmd[0] == "bob"
    assert "--chat-mode" in cmd
    assert out == "bob-echo"
    # and the prompt was piped via stdin (input=...), not as a positional
    assert "input" in fake_run.call_args.kwargs
    assert fake_run.call_args.kwargs["input"] == "system\n\nuser"


def test_bob_stub_default_unset_falls_through(monkeypatch):
    """Unset env var = real bob (default).  Same guard as the =0 case."""
    monkeypatch.delenv("ANTIKYTHERA_BOB_STUB", raising=False)
    lc_mod = _lc_mod()
    client = _make_bob_client()
    fake_result = MagicMock(returncode=0, stdout="x", stderr="")
    with patch.object(lc_mod.subprocess, "run", return_value=fake_result) as fake_run:
        client._chat_bob("s", "u", 0.7)
    assert fake_run.call_count == 1, "unset = default = real bob subprocess"


def test_bob_stub_executor_context_returns_tool_call_json(monkeypatch):
    """When the stub sees an Executor-Agent system prompt, it returns a
    parseable tool-call JSON (so the executor loop can route it)."""
    monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "1")
    client = _make_bob_client()
    import json
    out = client._chat_bob(
        "You are the Antikythera Executor Agent. Complete the task.",
        "Current Workspace Files:\nVERSION\n\nCurrent Task: do thing",
        0.7,
    )
    parsed = json.loads(out)   # must be valid JSON shaped {tool, args}
    assert "tool" in parsed and "args" in parsed


def test_bob_stub_planner_context_returns_checklist_array(monkeypatch):
    """When the stub sees a Planner system prompt, it returns a JSON array
    the planner's json.loads accepts."""
    monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "1")
    client = _make_bob_client()
    import json
    out = client._chat_bob(
        "You are the Antikythera Implementation Planner.",
        "### SPECIFICATION:\nx\n\n### ARCHITECTURE:\ny",
        0.7,
    )
    parsed = json.loads(out)
    assert isinstance(parsed, list) and parsed, "planner stub must yield a non-empty list"

