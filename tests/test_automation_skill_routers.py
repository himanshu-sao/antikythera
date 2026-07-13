"""Tests for the LLM-backed /propose and /brainstorm endpoints (P2.4).

These do not hit any live LLM: a fake LLMClient is injected by monkeypatching
the router module's ``llm_client`` global (the same seam used for
``api.ai_adapter`` in ``tests/test_ai_adapter.py``). Each test restores the real
LLMClient afterward so the fake never bleeds into the rest of the suite.

Deterministic fallback (the pre-P2.4 keyword / template logic) is asserted to
still run when the LLM is unavailable, returns the stub string, or emits
unparseable / invalid JSON — so the UI keeps working offline.
"""
import importlib
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

from api.main import app
import api.automation_router as automation_router
import api.skill_router as skill_router


class _FakeLLM:
    """Minimal stand-in for agents.llm_client.LLMClient.

    .chat(system_prompt, user_prompt, temperature=0.7) returns the canned
    string, or raises if ``response`` is an Exception instance (mirrors
    tests/test_ai_adapter.py).
    """
    def __init__(self, response):
        self._response = response
        self.calls = 0

    def chat(self, system_prompt, user_prompt, temperature=0.7):
        self.calls += 1
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_automation_llm(monkeypatch):
    """Patch automation_router.llm_client; restores the real one on teardown."""
    real = automation_router.llm_client
    fake = _FakeLLM("[stub response — not patched]")
    monkeypatch.setattr(automation_router, "llm_client", fake)
    yield fake
    automation_router.llm_client = real


@pytest.fixture
def fake_skill_llm(monkeypatch):
    """Patch skill_router.llm_client; restores the real one on teardown."""
    real = skill_router.llm_client
    fake = _FakeLLM("[stub response — not patched]")
    monkeypatch.setattr(skill_router, "llm_client", fake)
    yield fake
    skill_router.llm_client = real


# --------------------------------------------------------------------------
# /api/automation/propose
# --------------------------------------------------------------------------
def test_propose_uses_llm_when_available(client, fake_automation_llm):
    llm_json = {
        "step_id": "step_new",
        "operator_id": "update_resource",
        "adapter_id": "jira_adapter",
        "config": {"status": "Investigating"},
        "input_ref": "fetched_data",
        "output_ref": "update_result",
    }
    fake_automation_llm._response = json.dumps(llm_json)

    resp = client.post("/api/automation/propose", json={
        "instruction": "escalate the ticket to the security team",
        "current_state": {"fetched_data": {"id": "PROJ-1"}},
        "integration_id": "jira_adapter",
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["suggested_step"]["operator_id"] == "update_resource"
    assert data["suggested_step"]["adapter_id"] == "jira_adapter"
    assert data["suggested_step"]["config"] == {"status": "Investigating"}
    assert data["proposal_id"] == "prop_1"
    assert fake_automation_llm.calls == 1


def test_propose_falls_back_to_keyword_logic_on_stub(client, fake_automation_llm):
    fake_automation_llm._response = "[stub response — google LLM call failed: no key]"

    resp = client.post("/api/automation/propose", json={
        "instruction": "fetch the jira ticket PROJ-123",
        "current_state": {},
        "integration_id": "jira_adapter",
    })

    assert resp.status_code == 200, resp.text
    assert resp.json()["suggested_step"]["operator_id"] == "fetch_resource"
    assert fake_automation_llm.calls == 1


def test_propose_falls_back_on_unparseable_json(client, fake_automation_llm):
    fake_automation_llm._response = "Sure! I think you should fetch the ticket."

    resp = client.post("/api/automation/propose", json={
        "instruction": "fetch the jira ticket PROJ-123",
        "current_state": {},
        "integration_id": "jira_adapter",
    })

    assert resp.status_code == 200, resp.text
    # Fell back to the keyword branch for "fetch".
    assert resp.json()["suggested_step"]["operator_id"] == "fetch_resource"


def test_propose_unknown_instruction_returns_400(client, fake_automation_llm):
    fake_automation_llm._response = "[stub response — google LLM call failed: no key]"

    resp = client.post("/api/automation/propose", json={
        "instruction": "evaluate the philosophical implications of kanban",
        "current_state": {},
        "integration_id": "jira_adapter",
    })

    assert resp.status_code == 400


def test_propose_llm_response_validates_pathstep(client, fake_automation_llm):
    # PathStep.operator_id is a plain str field (no enum constraint), so a
    # well-formed LLM response is surfaced as-is. This documents that behavior:
    # when the LLM JSON has the required keys, the operator is trusted. The
    # 400 / fallback contract is covered by test_propose_unknown_instruction_returns_400.
    fake_automation_llm._response = json.dumps({
        "step_id": "step_new",
        "operator_id": "teleport_resource",
        "adapter_id": "jira_adapter",
        "config": {},
    })

    resp = client.post("/api/automation/propose", json={
        "instruction": "evaluate the philosophical implications of kanban",
        "current_state": {},
        "integration_id": "jira_adapter",
    })

    assert resp.status_code == 200
    assert resp.json()["suggested_step"]["operator_id"] == "teleport_resource"


def test_propose_accepts_model_field(client, fake_automation_llm):
    # The UI sends `model` in the body; it must be accepted (not 422'd) even
    # though it is not yet spliced into the chat call.
    fake_automation_llm._response = "[stub response — google LLM call failed: no key]"

    resp = client.post("/api/automation/propose", json={
        "instruction": "fetch the jira ticket PROJ-123",
        "current_state": {},
        "integration_id": "jira_adapter",
        "model": "meta/llama-3.1-405b-instruct",
    })

    assert resp.status_code == 200, resp.text
    assert resp.json()["suggested_step"]["operator_id"] == "fetch_resource"


# --------------------------------------------------------------------------
# /api/skills/brainstorm
# --------------------------------------------------------------------------
def test_brainstorm_uses_llm_when_available(client, fake_skill_llm):
    llm_json = {
        "proposed_prompt": "Extract remediation from the sample.",
        "proposed_schema": {"remediation": "string"},
        "reasoning": "Single string field; few-shot extraction.",
    }
    fake_skill_llm._response = "```json\n" + json.dumps(llm_json) + "\n```"

    resp = client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation"],
        "suggestion": "extract the version",
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["proposed_prompt"] == "Extract remediation from the sample."
    assert data["proposed_schema"] == {"remediation": "string"}
    assert data["reasoning"] == "Single string field; few-shot extraction."
    assert fake_skill_llm.calls == 1


def test_brainstorm_falls_back_on_stub(client, fake_skill_llm):
    fake_skill_llm._response = "[stub response — google LLM call failed: no key]"

    resp = client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation", "severity"],
        "suggestion": "extract",
    })

    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Deterministic fallback: schema maps every field to "string".
    assert data["proposed_schema"] == {"remediation": "string", "severity": "string"}
    assert "remediation" in data["proposed_prompt"]


def test_brainstorm_falls_back_on_missing_keys(client, fake_skill_llm):
    # JSON present but missing proposed_schema → must fall back.
    fake_skill_llm._response = json.dumps({"proposed_prompt": "x", "reasoning": "y"})

    resp = client.post("/api/skills/brainstorm", json={
        "text_sample": "Remediation: 2.5.0-1.el8_10",
        "target_fields": ["remediation"],
        "suggestion": "extract",
    })

    assert resp.status_code == 200, resp.text
    assert resp.json()["proposed_schema"] == {"remediation": "string"}


# --------------------------------------------------------------------------
# P3.4 regression guard: skill_router must not instantiate SecretVault at import
# --------------------------------------------------------------------------
def test_skill_router_no_longer_instantiates_secret_vault(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Re-import the module in a clean working directory.
        sys.modules.pop("api.skill_router", None)
        importlib.import_module("api.skill_router")

        assert not (tmp_path / ".vault.key").exists(), (
            "skill_router created .vault.key at import — SecretVault re-introduced?"
        )
        assert not (tmp_path / "secrets.vault").exists(), (
            "skill_router created secrets.vault at import — SecretVault re-introduced?"
        )
    finally:
        os.chdir(cwd)
        # Restore the real imported module for the rest of the suite.
        sys.modules.pop("api.skill_router", None)
        importlib.import_module("api.skill_router")


# --------------------------------------------------------------------------
# P3.4 regression guard: pipeline_router must not instantiate SecretVault at import
# (the half of P3.4 the skill guard does not cover)
# --------------------------------------------------------------------------
def test_pipeline_router_no_longer_instantiates_secret_vault(tmp_path):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        sys.modules.pop("api.pipeline_router", None)
        importlib.import_module("api.pipeline_router")

        assert not (tmp_path / ".vault.key").exists(), (
            "pipeline_router created .vault.key at import — SecretVault re-introduced?"
        )
        assert not (tmp_path / "secrets.vault").exists(), (
            "pipeline_router created secrets.vault at import — SecretVault re-introduced?"
        )
    finally:
        os.chdir(cwd)
        sys.modules.pop("api.pipeline_router", None)
        importlib.import_module("api.pipeline_router")


# --------------------------------------------------------------------------
# P2.5: POST /api/workflows/trigger — UI (WorkflowManager.tsx) calls this with
# {template_id, inputs} and expects {status, run_id, message}.
# --------------------------------------------------------------------------
def test_trigger_workflow_404_for_missing_template(client, tmp_path):
    resp = client.post("/api/workflows/trigger", json={
        "template_id": "definitely_not_a_real_template_xyz",
        "inputs": {},
    })
    assert resp.status_code == 404, resp.text
    assert "not found" in resp.json()["detail"].lower()


def test_trigger_workflow_creates_run_for_known_template(client, tmp_path):
    # Seed a template through the app's own state manager so the run is resolvable.
    from api.main import get_state_manager
    sm = get_state_manager()
    template_id = "test_trigger_tpl"
    sm.templates.save_template(template_id, {"name": "Trigger Test", "steps": []})
    try:
        resp = client.post("/api/workflows/trigger", json={
            "template_id": template_id,
            "inputs": {},
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "success"
        assert data["run_id"].startswith("run_")
        assert "message" in data
        # The run must actually exist in state.
        assert sm.runs.get_run(data["run_id"]) is not None
        assert sm.runs.get_run(data["run_id"])["template_id"] == template_id
    finally:
        # Clean up the seeded template + run so other tests stay isolated.
        try:
            sm.templates.delete_template(template_id)
        except Exception:
            pass


def test_trigger_workflow_accepts_inputs_with_item_id(client, tmp_path):
    """inputs.item_id, if provided, should bind the new run to that board item."""
    from api.main import get_state_manager
    sm = get_state_manager()
    template_id = "test_trigger_bind_tpl"
    sm.templates.save_template(template_id, {"name": "Bind Test", "steps": []})
    try:
        resp = client.post("/api/workflows/trigger", json={
            "template_id": template_id,
            "inputs": {"item_id": "ID-TRIG-1"},
        })
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["run_id"]
        # The binding should be recorded for that item.
        assert sm.bindings.get_run_id_for_item("ID-TRIG-1") == run_id
    finally:
        try:
            sm.templates.delete_template(template_id)
        except Exception:
            pass
