"""Tests for the real-LLM path and deterministic fallback of AIAdapter.analyze.

These do not hit any live LLM: a fake LLMClient is injected via the
``llm_client`` constructor param added in this change.
"""
import json
import pytest

from api.ai_adapter import AIAdapter


class _FakeLLM:
    """Minimal stand-in for agents.llm_client.LLMClient for analyze() tests."""
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def chat(self, system_prompt, user_prompt, temperature=0.7):
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_analyze_parses_llm_json_decision():
    decision = {
        "decision": "SCALE_UP",
        "reasoning": "traffic spike detected",
        "action_params": {"replicas": 5},
    }
    llm = _FakeLLM(json.dumps(decision))
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(prompt="decide autoscaling", context_data={"qps": 9000})

    assert result == decision
    assert llm.calls == 1


def test_analyze_tolerates_fenced_json_block():
    decision = {"decision": "CONTINUE", "reasoning": "ok", "action_params": {}}
    llm = _FakeLLM("```json\n" + json.dumps(decision) + "\n```")
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(prompt="x", context_data={})

    assert result == decision


def test_analyze_falls_back_when_llm_returns_stub():
    """When the shared LLM is unavailable it returns a 'stub response' string;
    analyze must route through the deterministic _simulate_llm_call instead.
    """
    llm = _FakeLLM("[stub response — openai LLM call failed: no key]")
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(prompt="x", context_data={"status": "healthy"})

    assert result["decision"] == "CONTINUE"
    assert llm.calls == 1  # the chat attempt was made before falling back


def test_analyze_falls_back_when_llm_returns_non_json():
    llm = _FakeLLM("Sorry, I can't help with that.")
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(prompt="x", context_data={})

    assert result["decision"] == "CONTINUE"


def test_analyze_falls_back_when_llm_raises():
    llm = _FakeLLM(RuntimeError("network down"))
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(prompt="x", context_data={})

    assert result["decision"] == "CONTINUE"


def test_simulate_llm_vulnerability_branch_preserved():
    """The historical SENSITIVE_BLOCK branch must still fire on fallback."""
    llm = _FakeLLM("[stub response — unavailable]")
    adapter = AIAdapter(llm_client=llm)

    result = adapter.analyze(
        prompt="x",
        context_data={"issue": "vulnerability", "note": "fix not available"},
    )

    assert result["decision"] == "SENSITIVE_BLOCK"
    assert result["action_params"]["assign_to"] == "security_lead"


def test_analyze_includes_few_shot_patterns_in_prompt():
    decision = {"decision": "PAUSE", "reasoning": "match", "action_params": {}}
    llm = _FakeLLM(json.dumps(decision))
    adapter = AIAdapter(llm_client=llm)

    adapter.analyze(
        prompt="decide",
        context_data={"k": "v"},
        patterns=[
            {"context": {"k": "v"}, "resolution": "paused it"},
        ],
    )

    assert llm.calls == 1
