"""Live-LLM smoke test of LLMClient against Gemma 4 (deselected by default).

Run with: pytest -m live_llm tests/test_ai_integration.py
Needs GOOGLE_API_KEY_KANBAN and network. Offline coverage of LLMClient lives in
tests/test_llm_client.py.
"""
import os

import pytest

# Deliberately does NOT load the project .env: a live test runs only when the
# caller exports GOOGLE_API_KEY_KANBAN explicitly (opt-in via -m live_llm).
pytestmark = pytest.mark.live_llm

MODELS = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]


@pytest.mark.parametrize("model_name", MODELS)
def test_llm_with_gemma_4(model_name):
    if not os.getenv("GOOGLE_API_KEY_KANBAN"):
        pytest.skip("GOOGLE_API_KEY_KANBAN not set")

    from agents.llm_client import LLMClient

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = LLMClient(config_path=os.path.join(root, "config.yaml"))
    client.model = model_name

    response = client.chat(
        system_prompt="You are a helpful assistant. Answer very briefly.",
        user_prompt="What is 2 + 2?",
    )

    assert isinstance(response, str)
    assert not LLMClient.is_stub(response), f"{model_name}: degraded to stub: {response[:120]}"
    assert "4" in response
