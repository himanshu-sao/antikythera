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
