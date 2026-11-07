import os
import yaml
import pytest

class _RaisingGenaiClient:
    """Fake google.genai.Client whose construction fails (e.g. no API key)."""

    def __init__(self, *args, **kwargs):
        raise ValueError("Missing key inputs argument")


class _FakeGenaiModels:
    def __init__(self, calls):
        self._calls = calls

    def generate_content(self, **kwargs):
        self._calls.append(kwargs)

        class _Resp:
            text = "fake google answer"

        return _Resp()


def _fake_genai_client_factory(calls):
    # ``models`` must be a class attribute: _chat_google checks
    # ``hasattr(genai.Client, "models")`` on the class.
    class _FakeGenaiClient:
        models = _FakeGenaiModels(calls)

        def __init__(self, api_key=None):
            self.api_key = api_key

    return _FakeGenaiClient


def _write_google_config(tmp_path, model="test-model"):
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": model}}, f)
    return config_path


def test_llm_client_chat(tmp_path, monkeypatch):
    """Google provider whose SDK client cannot be built degrades to the stub
    string. The degraded path is forced with a fake genai.Client; it does not
    depend on any shadow package or on a missing API key."""
    config_path = _write_google_config(tmp_path)
    import agents.llm_client as lc_mod
    # Force the config-service resolver to return None so this exercises the
    # config.yaml google path deterministically, independent of the ambient
    # ~/.antikythera/ai_config.json default.
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
    monkeypatch.setattr(lc_mod.genai, "Client", _RaisingGenaiClient)

    client = lc_mod.LLMClient(config_path=str(config_path))
    assert client.provider == "google"
    assert client.client is None  # construction failure -> None, not a raise

    response = client.chat("system", "user")
    assert isinstance(response, str)
    assert "stub response" in response.lower()
    assert lc_mod.LLMClient.is_stub(response)

    # generate_structured_content delegates to chat and returns the same stub.
    assert client.generate_structured_content("sys", "usr") == response


def test_llm_client_google_success_uses_fake_sdk(tmp_path, monkeypatch):
    """With a fake SDK client the google path returns the SDK text and passes
    the configured model; nothing reaches a real provider."""
    config_path = _write_google_config(tmp_path, model="fake-model")
    import agents.llm_client as lc_mod
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
    calls = []
    monkeypatch.setattr(lc_mod.genai, "Client", _fake_genai_client_factory(calls))

    client = lc_mod.LLMClient(config_path=str(config_path))
    out = client.chat("SYS", "USR", temperature=0.1)

    assert out == "fake google answer"
    assert len(calls) == 1
    assert calls[0]["model"] == "fake-model"
    assert calls[0]["contents"] == "USR"
    assert not lc_mod.LLMClient.is_stub(out)


def test_llm_client_google_sdk_error_degrades_to_stub(tmp_path, monkeypatch):
    """An exception raised by the SDK call is caught and returned as a stub."""
    config_path = _write_google_config(tmp_path)
    import agents.llm_client as lc_mod
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)

    class _M:
        @staticmethod
        def generate_content(**kwargs):
            raise RuntimeError("provider down")

    class _Boom:
        models = _M()

        def __init__(self, api_key=None):
            self.api_key = api_key

    monkeypatch.setattr(lc_mod.genai, "Client", _Boom)
    out = lc_mod.LLMClient(config_path=str(config_path)).chat("s", "u")
    assert lc_mod.LLMClient.is_stub(out)
    assert "provider down" in out


class _FakeOpenAI:
    """Replacement for the ``OpenAI`` name in agents.llm_client; no network."""

    instances = []

    def __init__(self, api_key=None, base_url=None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.calls = []
        _FakeOpenAI.instances.append(self)
        outer = self

        class _Completions:
            @staticmethod
            def create(**kwargs):
                outer.calls.append(kwargs)

                class _Msg:
                    content = "fake openai answer"

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def test_llm_client_uses_config_service_default(tmp_path, monkeypatch):
    """When AIEngineConfigService has a usable default, LLMClient should take
    that path (config-service first) instead of config.yaml. The resolver is
    monkeypatched and the OpenAI client is replaced by a fake, so no
    filesystem or network dependency remains.
    """
    # Point the config.yaml fallback at an unrelated value so the test would
    # FAIL if the fallback path were taken (proving the service wins).
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": "should-not-be-used"}}, f)

    from agents import llm_client as lc_mod

    _FakeOpenAI.instances = []
    monkeypatch.setattr(lc_mod, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: {
        "provider": "nvidia_nim",
        "model": "meta/llama-3.1-405b-instruct",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key": None,
    })

    client = lc_mod.LLMClient(config_path=str(config_path))
    assert client.provider == "nvidia_nim"
    assert client.model == "meta/llama-3.1-405b-instruct"
    assert "integrate.api.nvidia.com" in (client.base_url or "")
    # The (fake) OpenAI client was built with the service's base_url and a
    # placeholder key (no real key was supplied).
    assert len(_FakeOpenAI.instances) == 1
    fake = _FakeOpenAI.instances[0]
    assert "integrate.api.nvidia.com" in fake.base_url
    assert fake.api_key == "antikythera-missing-key"

    out = client.chat("s", "u")
    assert out == "fake openai answer"
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "meta/llama-3.1-405b-instruct"
    assert fake.calls[0]["messages"][0] == {"role": "system", "content": "s"}
    assert fake.calls[0]["messages"][1] == {"role": "user", "content": "u"}


def test_llm_client_openai_error_degrades_to_stub(tmp_path, monkeypatch):
    """A failing OpenAI-compatible call degrades to the stub string."""
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump({"llm": {"provider": "google", "model": "unused"}}, f)
    from agents import llm_client as lc_mod

    class _FailingOpenAI(_FakeOpenAI):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)

            class _C:
                @staticmethod
                def create(**kwargs):
                    raise RuntimeError("rate limited")

            self.chat.completions = _C()

    monkeypatch.setattr(lc_mod, "OpenAI", _FailingOpenAI)
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: {
        "provider": "nvidia_nim", "model": "m",
        "base_url": "https://integrate.api.nvidia.com/v1", "api_key": None,
    })
    out = lc_mod.LLMClient(config_path=str(config_path)).chat("s", "u")
    assert lc_mod.LLMClient.is_stub(out)
    assert "rate limited" in out


def test_llm_client_falls_back_to_config_when_service_unusable(tmp_path, monkeypatch):
    """When the config-service resolver returns None, fall back to config.yaml."""
    config_path = _write_google_config(tmp_path)
    from agents import llm_client as lc_mod
    monkeypatch.setattr(lc_mod, "_resolve_from_config_service", lambda: None)
    monkeypatch.setattr(lc_mod.genai, "Client", _RaisingGenaiClient)

    client = lc_mod.LLMClient(config_path=str(config_path))
    assert client.provider == "google"
    assert client.model == "test-model"
    # Fake SDK client could not be built -> degraded stub string.
    assert lc_mod.LLMClient.is_stub(client.chat("s", "u"))


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


