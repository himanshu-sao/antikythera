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

