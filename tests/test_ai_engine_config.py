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
from api.services.ai_engine_config import AIEngineConfigService, AIEngineConfigError


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


def test_test_ibm_bob_failure_uses_static_message_not_raw_stderr(tmp_path):
    """P2.6 security review: a non-zero exit must return a static message
    mapped from the exit code — raw subprocess stderr (which may contain
    auth hints or an MCP-discovery trail) must NOT reach the API caller."""
    svc = _make_service(tmp_path)
    cfg = svc.get_model_config("test-bob-model")

    fake = MagicMock(returncode=2, stdout="", stderr="secret-auth-trail")
    with patch("subprocess.run", return_value=fake):
        result = svc._test_ibm_bob(cfg)

    assert result["success"] is False
    assert "failed" in result["message"]  # static, code-mapped message
    assert "secret-auth-trail" not in result["message"]


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


# --------------------------------------------------------------------------
# SEC-9 / T5 / T28: the persistent .ai_env file is sourced by bash at startup,
# so every value must be inert under `source`, round-trip exactly, and the file
# must be 0600 from creation. Tests redirect the env path into tmp_path; they
# never touch the real ~/.antikythera.
# --------------------------------------------------------------------------
import os
import stat
import subprocess

from api.services import ai_engine_config as _aec


_PROVIDER_PREFIXES = ("NVIDIA_", "GOOGLE_", "IBM_BOB_", "OPENAI_", "ANTHROPIC_", "OLLAMA_", "OPENROUTER_")


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """Redirect the persistent env file to tmp_path before the service is built.

    Provider-prefixed variables inherited from the host shell are removed for the
    duration of the test (monkeypatch restores them) so no real key is ever copied
    into the tmp file.
    """
    target = tmp_path / ".ai_env"
    monkeypatch.setattr(
        _aec.AIEngineConfigService, "_persistent_env_path", lambda self: str(target)
    )
    for key in list(os.environ):
        if key.startswith(_PROVIDER_PREFIXES):
            monkeypatch.delenv(key, raising=False)
    return target


def _svc(tmp_path):
    return AIEngineConfigService(config_path=str(tmp_path / "ai_config.json"))


def _bash_source_then(path, snippet, env_name=None):
    """Run ``bash -c 'source <path>; <snippet>'`` with a clean environment."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}
    return subprocess.run(
        ["bash", "-c", 'source "$1"; ' + snippet, "bash", str(path)],
        capture_output=True, text=True, env=env, timeout=20,
    )


class TestPersistentEnvSafety:
    def test_command_substitution_and_backticks_are_inert(self, tmp_path, env_file, monkeypatch):
        sentinel = tmp_path / "sentinel"
        hostile = f"abc$(touch {sentinel})def`touch {sentinel}`ghi"
        monkeypatch.setenv("NVIDIA_API_KEY", hostile)
        svc = _svc(tmp_path)
        svc._write_persistent_env()
        assert env_file.exists()
        result = _bash_source_then(env_file, "true")
        assert result.returncode == 0
        assert not sentinel.exists(), "sourcing the env file executed a command substitution"

    def test_value_round_trips_exactly_through_bash(self, tmp_path, env_file, monkeypatch):
        values = [
            'plain-value-123',
            "it's-quoted",
            'dq"inside',
            'back\\slash',
            'dollar$HOME-not-expanded',
            "mix'\"$(id)`x`\\",
        ]
        # Build the service once: its constructor loads the env file into os.environ,
        # which would otherwise clobber the value set for the next iteration.
        svc = _svc(tmp_path)
        for value in values:
            monkeypatch.setenv("NVIDIA_API_KEY", value)
            svc._write_persistent_env()
            result = _bash_source_then(env_file, 'printf %s "$NVIDIA_API_KEY"')
            assert result.returncode == 0
            assert result.stdout == value, "bash did not reproduce the stored value exactly"  # synthetic test values only

    def test_env_file_mode_is_0600(self, tmp_path, env_file, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "x")
        _svc(tmp_path)._write_persistent_env()
        assert stat.S_IMODE(os.stat(env_file).st_mode) == 0o600

    def test_no_world_readable_window_on_overwrite(self, tmp_path, env_file, monkeypatch):
        # A pre-existing, world-readable file must be replaced by a 0600 file, never
        # written through with its old permissions.
        env_file.write_text("old\n")
        os.chmod(env_file, 0o644)
        monkeypatch.setenv("NVIDIA_API_KEY", "x")
        _svc(tmp_path)._write_persistent_env()
        assert stat.S_IMODE(os.stat(env_file).st_mode) == 0o600

    def test_no_temp_files_left_behind(self, tmp_path, env_file, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "x")
        _svc(tmp_path)._write_persistent_env()
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith(".tmp")]
        assert leftovers == []

    def test_newline_in_value_is_refused(self, tmp_path, env_file, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "good")
        svc = _svc(tmp_path)
        svc._write_persistent_env()
        monkeypatch.setenv("NVIDIA_API_KEY", "line1\nNVIDIA_EVIL=1")
        svc._write_persistent_env()  # must not raise, must not write the injected line
        text = env_file.read_text()
        injected = "NVIDIA_EVIL" in text or "line1" in text
        assert not injected, "newline in value produced an extra line in the env file"

    def test_nul_in_value_is_refused(self, tmp_path, env_file):
        # os.environ cannot hold NUL, so exercise the formatter directly.
        with pytest.raises(ValueError):
            _aec._format_env_line("NVIDIA_API_KEY", "bad\x00value")
        with pytest.raises(ValueError):
            _aec._format_env_line("NVIDIA_API_KEY", "bad\nvalue")
        with pytest.raises(ValueError):
            _aec._format_env_line("NVIDIA_API_KEY", "bad\rvalue")
        with pytest.raises(ValueError):
            _aec._format_env_line("NOT-A-NAME", "x")

    def test_set_api_key_rejects_newline_before_mutating_env(self, tmp_path, env_file, monkeypatch):
        svc = _svc(tmp_path)
        model_id = "nim-test-model"
        svc.add_model(ModelConfig(
            model_id=model_id, provider=AIProvider.NVIDIA_NIM, name="n",
            api_key_env="NVIDIA_API_KEY_SEC9",
        ))
        monkeypatch.delenv("NVIDIA_API_KEY_SEC9", raising=False)
        with pytest.raises(AIEngineConfigError):
            svc.set_api_key(model_id, "line1\nINJECTED=1")
        assert "NVIDIA_API_KEY_SEC9" not in os.environ

    def test_set_api_key_writes_safe_file_for_hostile_value(self, tmp_path, env_file, monkeypatch):
        sentinel = tmp_path / "sentinel2"
        svc = _svc(tmp_path)
        model_id = "nim-test-model-2"
        svc.add_model(ModelConfig(
            model_id=model_id, provider=AIProvider.NVIDIA_NIM, name="n",
            api_key_env="NVIDIA_API_KEY_SEC9B",
        ))
        monkeypatch.delenv("NVIDIA_API_KEY_SEC9B", raising=False)
        svc.set_api_key(model_id, f"$(touch {sentinel})`touch {sentinel}`")
        monkeypatch.delenv("NVIDIA_API_KEY_SEC9B", raising=False)
        _bash_source_then(env_file, "true")
        assert not sentinel.exists()
        assert stat.S_IMODE(os.stat(env_file).st_mode) == 0o600


class TestPersistentEnvLoaderRoundTrip:
    def test_python_loader_reads_back_quoted_values(self, tmp_path, env_file, monkeypatch):
        value = "it's $(x) `y` \"z\" back\\slash"
        monkeypatch.setenv("NVIDIA_API_KEY", value)
        _svc(tmp_path)._write_persistent_env()
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
        _svc(tmp_path)  # constructor runs _load_persistent_env
        assert os.environ.get("NVIDIA_API_KEY") == value
        monkeypatch.delenv("NVIDIA_API_KEY", raising=False)


class TestPersistentEnvCreateFlags:
    def test_temp_file_created_exclusively_with_0600(self, tmp_path, env_file, monkeypatch):
        seen = []
        real_open = os.open

        def spy(path, flags, mode=0o777, *a, **kw):
            if str(path).startswith(str(env_file)) and str(path).endswith(".tmp"):
                seen.append((flags, mode))
            return real_open(path, flags, mode, *a, **kw)

        monkeypatch.setattr(_aec.os, "open", spy)
        monkeypatch.setenv("NVIDIA_API_KEY", "x")
        _svc(tmp_path)._write_persistent_env()
        assert seen, "temp file was not created through os.open"
        flags, mode = seen[-1]
        assert flags & os.O_EXCL, "temp file must be created with O_EXCL"
        assert flags & os.O_CREAT
        assert mode == 0o600
