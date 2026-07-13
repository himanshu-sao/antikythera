"""Tests for the ibm_bob-specific behaviour in ``AIEngineConfigService``.

P2.6 changed ibm_bob from an HTTP provider to the local ``bob`` CLI binary
(see CLAUDE.md gotcha #10). These tests pin the new contract:

  * ``_test_ibm_bob`` shells out to ``bob`` (no HTTP), returns the standard
    ``{success, message, [details]}`` shape, and handles a missing binary /
    timeout gracefully.
  * ``_list_ibm_bob_models`` returns the statically-configured model id
    (the ``bob`` CLI has no ``--list-models`` command).
  * ibm_bob is excluded from the ``needs_api_key`` gate — no HTTP API key
    is required, so connectivity must not be blocked on a missing key.
"""
import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from api.models.config import AIProvider, ModelConfig
from api.services.ai_engine_config import AIEngineConfigService


def _make_service(tmp_path, model_id="test-bob-model", provider=AIProvider.IBM_BOB,
                  api_key_env=None):
    """Build an isolated AIEngineConfigService with one model configured.

    Writes a throwaway ``ai_config.json`` under the pytest tmp dir so the
    service never touches ``~/.antikythera/ai_config.json``.
    """
    cfg_path = tmp_path / "ai_config.json"
    model = {
        "model_id": model_id,
        "provider": provider.value,
        "name": "Test Bob Model",
        "api_key_env": api_key_env,
    }
    with open(cfg_path, "w") as f:
        json.dump({"models": {model_id: model}}, f)
    return AIEngineConfigService(config_path=str(cfg_path))


# ---------------------------------------------------------------------------
# _test_ibm_bob
# ---------------------------------------------------------------------------
def test_test_ibm_bob_success_shells_out(tmp_path):
    """A responsive ``bob`` binary (rc 0) yields a success result. No HTTP."""
    svc = _make_service(tmp_path)
    cfg = svc.get_model_config("test-bob-model")

    fake = MagicMock(returncode=0, stdout="pong\n", stderr="")
    with patch("subprocess.run", return_value=fake) as run:
        result = svc._test_ibm_bob(cfg)

    assert result["success"] is True
    assert "bob CLI responsive" in result["message"]
    # The command must target the bob binary with the verified flags.
    argv = run.call_args[0][0]
    assert argv[0] == "bob"
    assert "--chat-mode" in argv and "ask" in argv
    assert "--allowed-mcp-server-names" in argv  # suppresses MCP discovery
    assert "-o" in argv and "text" in argv
    # A configured model_id is passed via -m; "ping" is the smoke prompt.
    assert "-m" in argv and "test-bob-model" in argv
    assert "ping" in argv


def test_test_ibm_bob_failure_reports_stderr(tmp_path):
    """A non-zero exit surfaces the stderr in the message (no exception)."""
    svc = _make_service(tmp_path)
    cfg = svc.get_model_config("test-bob-model")

    fake = MagicMock(returncode=2, stdout="", stderr="auth expired")
    with patch("subprocess.run", return_value=fake):
        result = svc._test_ibm_bob(cfg)

    assert result["success"] is False
    assert "exited 2" in result["message"]
    assert "auth expired" in result["message"]


def test_test_ibm_bob_missing_binary(tmp_path):
    """If ``bob`` is not on PATH, return a clean failure (no crash)."""
    svc = _make_service(tmp_path)
    cfg = svc.get_model_config("test-bob-model")

    def raise_fnf(*a, **k):
        raise FileNotFoundError()

    with patch("subprocess.run", side_effect=raise_fnf):
        result = svc._test_ibm_bob(cfg)

    assert result["success"] is False
    assert "not found" in result["message"].lower()


def test_test_ibm_bob_timeout(tmp_path):
    """A first-run browser-SSO can be slow; a timeout is reported, not raised."""
    svc = _make_service(tmp_path)
    cfg = svc.get_model_config("test-bob-model")

    with patch("subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="bob", timeout=30)):
        result = svc._test_ibm_bob(cfg)

    assert result["success"] is False
    assert "timed out" in result["message"].lower()


# ---------------------------------------------------------------------------
# _list_ibm_bob_models
# ---------------------------------------------------------------------------
def test_list_ibm_bob_models_returns_static_id(tmp_path):
    """No ``--list-models`` in the bob CLI — the only available model is the
    one configured in ai_config.json, returned as a single-element list."""
    svc = _make_service(tmp_path, model_id="configured-bob-1")
    cfg = svc.get_model_config("configured-bob-1")
    assert svc._list_ibm_bob_models(cfg) == ["configured-bob-1"]


def test_list_ibm_bob_models_no_api_key_required(tmp_path):
    """Listing ibm_bob models must NOT raise for a missing API key (it never
    made an HTTP call in the first place)."""
    svc = _make_service(tmp_path, api_key_env="BOBSHELL_API_KEY")
    cfg = svc.get_model_config("test-bob-model")
    # No env var set; the static-id path still returns the model id cleanly.
    with patch.dict("os.environ", {}, clear=True):
        assert svc._list_ibm_bob_models(cfg) == ["test-bob-model"]


# ---------------------------------------------------------------------------
# needs_api_key gate (test_connection + list_available_models)
# ---------------------------------------------------------------------------
def test_test_connection_does_not_block_ibm_bob_on_missing_key(tmp_path):
    """ibm_bob is excluded from needs_api_key, so test_connection must proceed
    to the smoke test instead of short-circuiting on a missing key."""
    svc = _make_service(tmp_path, api_key_env="BOBSHELL_API_KEY")
    # No key set in env.
    fake = MagicMock(returncode=0, stdout="ok", stderr="")
    with patch.dict("os.environ", {}, clear=True), \
         patch("subprocess.run", return_value=fake):
        result = svc.test_connection("test-bob-model")
    assert result["success"] is True  # would be False if the key gate still fired


def test_list_available_models_marks_ibm_bob_key_as_set(tmp_path):
    """With ibm_bob out of needs_key and no api_key_env configured, the UI
    list should mark api_key_set=True (no key needed)."""
    svc = _make_service(tmp_path, api_key_env=None)
    models = svc.list_available_models()
    bob = next(m for m in models if m["provider"] == "ibm_bob")
    assert bob["api_key_set"] is True
