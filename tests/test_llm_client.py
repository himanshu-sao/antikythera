import os
import yaml
import pytest

def test_llm_client_chat(tmp_path, monkeypatch):
    # Write a minimal config.yaml pointing to the google stub
    config_path = tmp_path / "config.yaml"
    config_content = {"llm": {"provider": "google", "model": "test-model"}}
    with open(config_path, "w") as f:
        yaml.safe_dump(config_content, f)
    # Import LLMClient after creating config
    from agents.llm_client import LLMClient
    import agents.llm_client as lc_mod
    # Force the config-service resolver to return None so this exercises the
    # config.yaml google stub path deterministically — independent of the
    # ambient ~/.antikythera/ai_config.json default (which may point at a
    # reachable, keyed provider and so skip the stub). Same seam the sibling
    # tests below use (lines ~73/~86).
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
    client = LLMClient(config_path=str(config_path))
    # The stub client returns "stub response"
    response = client.chat("system", "user")
    assert isinstance(response, str)
    assert "stub" in response.lower()

    # generate_structured_content should delegate to chat with lower temperature
    struct = client.generate_structured_content("sys", "usr")
    assert struct == response


def test_llm_client_uses_config_service_default(tmp_path, monkeypatch):
    """When AIEngineConfigService has a usable default, LLMClient should take
    that path (config-service first) instead of config.yaml — this is the core
    wiring the plan closes. We monkeypatch the resolver to avoid any
    filesystem / network dependency.
    """
    # Point the config.yaml fallback at an unrelated value so the test would
    # FAIL if the fallback path were taken (proving the service wins).
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": "should-not-be-used"}}, f)

    from api.models.config import AIProvider, ModelConfig

    fake_model = ModelConfig(
        model_id="meta/llama-3.1-405b-instruct",
        provider=AIProvider.NVIDIA_NIM,
        name="NVIDIA Nemotron",
        endpoint_url="https://integrate.api.nvidia.com/v1",
        api_key_env=None,  # no key -> OpenAI client still constructs
        context_window=8192,
        provider_config={"base_url": "https://integrate.api.nvidia.com/v1"},
    )

    # Force the lazy resolver inside _resolve_from_config_service to reach our fake.
    from agents import llm_client as lc_mod
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: {
        "provider": fake_model.provider.value,
        "model": fake_model.model_id,
        "base_url": fake_model.provider_config["base_url"],
        "api_key": None,
    })

    client = lc_mod.LLMClient(config_path=str(config_path))
    assert client.provider == "nvidia_nim"
    assert client.model == "meta/llama-3.1-405b-instruct"
    assert "integrate.api.nvidia.com" in (client.base_url or "")
    # chat() degrades gracefully (no live key) but must not raise and stays a string.
    out = client.chat("s", "u")
    assert isinstance(out, str)


def test_llm_client_falls_back_to_config_when_service_unusable(tmp_path, monkeypatch):
    """When the config-service resolver returns None, fall back to config.yaml."""
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": "test-model"}}, f)

    from agents import llm_client as lc_mod
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)

    client = lc_mod.LLMClient(config_path=str(config_path))
    assert client.provider == "google"
    assert client.model == "test-model"
    # google stub path still yields a stub string.
    assert "stub" in client.chat("s", "u").lower()


def _make_bob_client(tmp_path, monkeypatch, model=None, config_service_disabled=True):
    """Build an LLMClient pointed at the ibm_bob provider via config.yaml.

    These tests assert the *real* ``bob`` subprocess path (flags, stdin, rc),
    so opt out of the session-wide ``ANTIKYTHERA_BOB_STUB=1`` default here.
    (The stub seam is unit-tested separately in test_bob_stub_seam.py.)
    """
    from agents import llm_client as lc_mod
    monkeypatch.setenv("ANTIKYTHERA_BOB_STUB", "0")
    if config_service_disabled:
        monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
    config_path = tmp_path / "config.yaml"
    llm_cfg = {"provider": "ibm_bob"}
    if model is not None:
        llm_cfg["model"] = model
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": llm_cfg}, f)
    return lc_mod, lc_mod.LLMClient(config_path=str(config_path))


class _FakeCompleted:
    def __init__(self, returncode=0, stdout="answer\n", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_ibm_bob_does_not_build_openai_client(tmp_path, monkeypatch):
    """ibm_bob is CLI-based: no OpenAI HTTP client should ever be constructed."""
    lc_mod, client = _make_bob_client(tmp_path, monkeypatch)
    assert client.provider == "ibm_bob"
    assert client.client is None
    assert not client.model  # None / "" — we do not fabricate a default model id


def test_ibm_bob_chat_invokes_bob_cli_with_verified_flags(tmp_path, monkeypatch):
    """_chat_bob must shell out to ``bob`` with the flags verified against
    ``bob --help`` (--chat-mode ask, empty MCP allow-list,
    --hide-intermediary-output, -o text) and must NOT use the deprecated -p.
    The prompt is piped via stdin (subprocess ``input=``) rather than passed
    as a positional after a ``--`` terminator: the terminator does NOT work on
    bob v1.0.6 (the positional after ``--`` is ignored and the binary exits 1
    "No input provided ... use the --prompt option"). Stdin also keeps a
    leading-dash prompt from being reinterpreted as a flag (P2.6 security review).
    """
    lc_mod, client = _make_bob_client(tmp_path, monkeypatch, model="some-model")
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        captured["input"] = kwargs.get("input")
        return _FakeCompleted(stdout="\nreal completion\n")

    monkeypatch.setattr(lc_mod.subprocess, "run", fake_run)
    out = client.chat("SYS", "USR")

    cmd = captured["cmd"]
    assert cmd[0] == "bob"
    # Verified-good flags are all present.
    assert "--chat-mode" in cmd and "ask" in cmd
    assert "--allowed-mcp-server-names" in cmd
    assert "" in cmd  # empty allow-list value suppresses MCP discovery
    assert "--hide-intermediary-output" in cmd
    assert "-o" in cmd and "text" in cmd
    # Model is passed only when configured.
    assert "-m" in cmd and "some-model" in cmd
    # Deprecated -p must NOT be used.
    assert "-p" not in cmd
    # The prompt is NOT passed as a positional: bob v1.0.6 misreads a positional
    # after ``--`` and exits 1. It must be piped via stdin instead.
    assert "--" not in cmd
    assert "SYS\n\nUSR" not in cmd
    assert captured["input"] == "SYS\n\nUSR"
    # The model value is the last argv element — no user-controlled positional
    # trails ``-m some-model`` (the prompt only travels via stdin).
    assert cmd[-1] == "some-model"
    assert cmd.index("some-model") == len(cmd) - 1
    # stdout is returned (stripped).
    assert out == "real completion"


def test_ibm_bob_chat_omits_m_when_no_model(tmp_path, monkeypatch):
    """With no model configured we omit -m so bob uses its own default —
    passing a fabricated id crashes the binary (rc 1, 'critical error')."""
    lc_mod, client = _make_bob_client(tmp_path, monkeypatch)  # model=None
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        return _FakeCompleted(stdout="ok\n")

    monkeypatch.setattr(lc_mod.subprocess, "run", fake_run)
    client.chat("s", "u")
    assert "-m" not in captured["cmd"]


def test_ibm_bob_chat_rejects_model_id_starting_with_dash(tmp_path, monkeypatch):
    """Security (P2.6 review): a model id that could masquerade as a bob
    option (leading ``-``) must be rejected by _chat_bob before shelling out,
    even though config.yaml bypasses ModelConfig's boundary validator. The
    rejection degrades to the stub string (pipeline never breaks)."""
    lc_mod, client = _make_bob_client(tmp_path, monkeypatch, model="--yolo")
    monkeypatch.setattr(
        lc_mod.subprocess, "run",
        lambda *a, **k: pytest.fail("must not shell out"),
    )
    out = client.chat("s", "u")
    assert "stub" in out.lower()


def test_ibm_bob_chat_nonzero_exit_degrades_to_stub(tmp_path, monkeypatch):
    """A bob CLI failure (rc != 0) must raise RuntimeError out of _chat_bob,
    which chat() catches and degrades to a stub string (pipeline never breaks).
    P2.6 security review: stderr is logged server-side only, NOT included in
    the stub/exception message returned to callers."""
    lc_mod, client = _make_bob_client(tmp_path, monkeypatch, model="m")
    monkeypatch.setattr(
        lc_mod.subprocess, "run",
        lambda *a, **k: _FakeCompleted(returncode=1, stderr="secret-auth-trail"),
    )
    out = client.chat("s", "u")
    assert isinstance(out, str)
    assert "stub" in out.lower()
    # Raw subprocess stderr must NOT leak into the caller-visible message.
    assert "secret-auth-trail" not in out


