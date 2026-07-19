"""Targeted tests for the P2.4 wiring of automation_router /propose and
skill_router /brainstorm through LLMClient.chat(), and their deterministic
fallbacks.

Mirrors the single-router isolation pattern in tests/test_observer.py: each
fixture builds a throwaway FastAPI() mounting just the router under test. A
fake LLMClient (with a recording .chat()) is injected via the module-level
``_llm`` slot so ``_get_llm()`` returns it without ever constructing a real
LLMClient — no live LLM key is needed.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import automation_router, skill_router


class _FakeLLM:
    """Minimal stand-in for LLMClient: records calls, returns canned chat() output."""

    def __init__(self, chat_return=""):
        self.chat_return = chat_return
        self.calls = []  # list of (system_prompt, user_prompt, temperature)

    def chat(self, system_prompt, user_prompt, temperature=0.7):
        self.calls.append((system_prompt, user_prompt, temperature))
        if isinstance(self.chat_return, Exception):
            raise self.chat_return
        return self.chat_return


# ---------------------------------------------------------------------------
# automation_router /propose
# ---------------------------------------------------------------------------

@pytest.fixture
def automation_client():
    app = FastAPI()
    app.include_router(automation_router.router, prefix="/api/automation")
    return TestClient(app)


def _install_fake_automation_llm(monkeypatch, fake):
    # _get_llm() returns the module-level _llm as-is when already set, so seeding
    # it avoids constructing a real LLMClient.
    monkeypatch.setattr(automation_router, "_llm", fake)


def test_propose_happy_path_uses_llm(automation_client, monkeypatch):
    """Valid LLM JSON is shaped into a ProposalResponse; chat() was actually called."""
    fake = _FakeLLM(chat_return=(
        '{"step_id": "step_new", "operator_id": "fetch_resource", '
        '"adapter_id": "jira_adapter", "mode": "adapter", '
        '"config": {"params": {}}, "input_ref": "resource_id", '
        '"output_ref": "fetched_data", "condition": null, "loop_over": null, '
        '"reasoning": "LLM mapped fetch instruction."}'
    ))
    _install_fake_automation_llm(monkeypatch, fake)

    res = automation_client.post("/api/automation/propose", json={
        "instruction": "fetch the jira ticket summary",
        "current_state": {"step_1": "done"},
        "integration_id": "jira_adapter",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["proposal_id"] == "prop_1"
    assert body["reasoning"] == "LLM mapped fetch instruction."
    step = body["suggested_step"]
    assert step["operator_id"] == "fetch_resource"
    assert step["adapter_id"] == "jira_adapter"
    assert step["output_ref"] == "fetched_data"
    # The wiring actually invoked chat() with the new system prompt.
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == automation_router._PROPOSER_SYSTEM
    assert fake.calls[0][2] == 0.2


def test_propose_llm_exception_falls_back(automation_client, monkeypatch):
    """If chat() raises, the deterministic simulation still returns 200."""
    fake = _FakeLLM(chat_return=RuntimeError("provider down"))
    _install_fake_automation_llm(monkeypatch, fake)

    res = automation_client.post("/api/automation/propose", json={
        "instruction": "fetch the data",
        "current_state": {},
    })
    assert res.status_code == 200
    body = res.json()
    # Simulation's fetch branch: fetch_resource + fetched_data output_ref.
    assert body["suggested_step"]["operator_id"] == "fetch_resource"
    assert body["suggested_step"]["output_ref"] == "fetched_data"
    assert "retrieve data" in body["reasoning"]
    assert len(fake.calls) == 1  # it tried the LLM first


def test_propose_llm_stub_string_falls_back(automation_client, monkeypatch):
    """The 'stub response' phrase means no real LLM — simulation is used."""
    fake = _FakeLLM(chat_return="[stub response — openai LLM call failed: no key]")
    _install_fake_automation_llm(monkeypatch, fake)

    res = automation_client.post("/api/automation/propose", json={
        "instruction": "update the status",
        "current_state": {},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["suggested_step"]["operator_id"] == "update_resource"
    assert body["suggested_step"]["config"]["status"] == "Investigating"


def test_propose_llm_non_json_falls_back(automation_client, monkeypatch):
    """Prose/Markdown instead of JSON → simulation used, 200."""
    fake = _FakeLLM(chat_return="Sure! I'd propose fetching the ticket.")
    _install_fake_automation_llm(monkeypatch, fake)

    res = automation_client.post("/api/automation/propose", json={
        "instruction": "get the issue",
        "current_state": {},
    })
    assert res.status_code == 200
    assert res.json()["suggested_step"]["operator_id"] == "fetch_resource"


def test_propose_simulate_unknown_instruction_returns_400(automation_client, monkeypatch):
    """The simulation's 'unknown instruction' branch still raises 400."""
    fake = _FakeLLM(chat_return="not json at all")
    _install_fake_automation_llm(monkeypatch, fake)

    # Instruction deliberately avoids every simulation keyword: extract/field/data,
    # if/then/update, each/all/every, fetch/get, update/change.
    res = automation_client.post("/api/automation/propose", json={
        "instruction": "sing a song about the ocean",
        "current_state": {},
    })
    assert res.status_code == 400


def test_propose_simulate_extract_branch(automation_client, monkeypatch):
    """Degraded path keeps the run_script extract branch intact."""
    fake = _FakeLLM(chat_return=None)  # _strip_and_parse_json(None) -> None -> fallback
    _install_fake_automation_llm(monkeypatch, fake)

    res = automation_client.post("/api/automation/propose", json={
        "instruction": "EXTRACT the field from the data",
        "current_state": {},
    })
    assert res.status_code == 200
    step = res.json()["suggested_step"]
    assert step["operator_id"] == "run_script"
    assert step["mode"] == "script"
    assert "code" in step["config"]


# ---------------------------------------------------------------------------
# skill_router /brainstorm
# ---------------------------------------------------------------------------

@pytest.fixture
def skill_client():
    app = FastAPI()
    app.include_router(skill_router.router, prefix="/api/skills")
    return TestClient(app)


def _install_fake_skill_llm(monkeypatch, fake):
    monkeypatch.setattr(skill_router, "_llm", fake)


def test_brainstorm_happy_path_uses_llm(skill_client, monkeypatch):
    fake = _FakeLLM(chat_return=(
        '{"proposed_prompt": "Extract remediation + cvss from text.", '
        '"proposed_schema": {"remediation": "string", "cvss": "number"}, '
        '"reasoning": "LLM authored a few-shot extractor for both fields."}'
    ))
    _install_fake_skill_llm(monkeypatch, fake)

    res = skill_client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10, CVSS: 7.5",
        "target_fields": ["remediation", "cvss"],
        "suggestion": "extract both",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["proposed_prompt"] == "Extract remediation + cvss from text."
    assert body["proposed_schema"] == {"remediation": "string", "cvss": "number"}
    assert body["reasoning"].startswith("LLM authored")
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == skill_router._BRAINSTORM_SYSTEM
    assert fake.calls[0][2] == 0.2


def test_brainstorm_llm_exception_falls_back(skill_client, monkeypatch):
    fake = _FakeLLM(chat_return=RuntimeError("no key"))
    _install_fake_skill_llm(monkeypatch, fake)

    res = skill_client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation"],
        "suggestion": "extract remediation",
    })
    assert res.status_code == 200
    body = res.json()
    # Simulation's few-shot template + {field: "string"} schema.
    assert "structured data extractor" in body["proposed_prompt"]
    assert body["proposed_schema"] == {"remediation": "string"}
    assert set(body["proposed_schema"]) == {"remediation"}
    assert len(fake.calls) == 1


def test_brainstorm_llm_stub_string_falls_back(skill_client, monkeypatch):
    fake = _FakeLLM(chat_return="[stub response — google LLM call failed: no key]")
    _install_fake_skill_llm(monkeypatch, fake)

    res = skill_client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation"],
        "suggestion": "extract remediation",
    })
    assert res.status_code == 200
    assert "structured data extractor" in res.json()["proposed_prompt"]


def test_brainstorm_llm_schema_missing_target_field_falls_back(skill_client, monkeypatch):
    """If the LLM omits a requested target field from proposed_schema, fall back."""
    fake = _FakeLLM(chat_return=(
        '{"proposed_prompt": "x", '
        '"proposed_schema": {"remediation": "string"}, '
        '"reasoning": "r"}'  # schema missing "cvss"
    ))
    _install_fake_skill_llm(monkeypatch, fake)

    res = skill_client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation", "cvss"],
        "suggestion": "extract both",
    })
    assert res.status_code == 200
    # Simulation populates ALL target fields.
    assert set(res.json()["proposed_schema"]) == {"remediation", "cvss"}
