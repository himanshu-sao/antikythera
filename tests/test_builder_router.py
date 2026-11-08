"""S12 / P2-11: the Blueprint builder must use real LLM output and must only
produce templates that the workflow save validators accept.

Defects (verified at HEAD):
- generate used the LLM reply only when the decision text contained the literal
  word "JSON", and analyze() discards the template JSON, so the keyword fallbacks
  always won;
- the fallback templates used shell steps (B1 rejects), jira config keys that fail
  the B2 schema, and a github internal step without ``action``, so none could be saved.

Fix under test:
- generate parses a JSON object (bare or fenced) that has name, trigger and steps;
  anything else (prose, stub, error, bad JSON, missing keys) falls back;
- every fallback template passes _validate_template_adapters and _validate_step_configs;
- POST /api/builder/validate applies the same two validators and returns
  status "invalid" with the violations.

The LLM is always a fake (no provider, no network).
"""
import copy
import json

import pytest
from fastapi.testclient import TestClient

# Import the app first: workflow_router imports api.main, which imports this
# module. Importing builder_router cold would hit that cycle.
from api.main import app  # noqa: F401  (import order matters)
from api import builder_router
from api.builder_router import GenerationRequest, _fallback_template, _parse_template_reply
from api.workflow_router import _validate_step_configs, _validate_template_adapters


VALID_TEMPLATE = {
    "name": "LLM Template",
    "description": "from the model",
    "trigger": {"type": "webhook", "provider": "github", "config": {}},
    "steps": [
        {"id": 1, "adapter": "github", "action": "list_repos",
         "config": {"org": "acme"}, "board_stage": "EXECUTING"},
        {"id": 2, "adapter": "internal", "action": "add_comment",
         "config": {"action": "add_comment", "body": "done"}, "board_stage": "DONE"},
    ],
}


class FakeLLM:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []

    def chat(self, system_prompt, user_prompt, temperature=0.7):
        self.calls.append((system_prompt, user_prompt))
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_llm(monkeypatch):
    holder = {"llm": FakeLLM(reply="")}

    def install(reply=None, error=None):
        holder["llm"] = FakeLLM(reply=reply, error=error)
        monkeypatch.setattr(builder_router.ai_engine, "_llm", holder["llm"])
        return holder["llm"]

    monkeypatch.setattr(builder_router.ai_engine, "_llm", holder["llm"])
    return install


def _generate(client, prompt="Please create a github merge release workflow"):
    return client.post("/api/builder/generate", json={"prompt": prompt, "template_name": "Mine"})


# -- parsing -----------------------------------------------------------------

class TestParseTemplateReply:
    def test_bare_json_object_is_accepted(self):
        assert _parse_template_reply(json.dumps(VALID_TEMPLATE)) == VALID_TEMPLATE

    def test_json_fence_is_accepted(self):
        text = "```json\n" + json.dumps(VALID_TEMPLATE, indent=2) + "\n```"
        assert _parse_template_reply(text) == VALID_TEMPLATE

    def test_plain_fence_is_accepted(self):
        text = "```\n" + json.dumps(VALID_TEMPLATE) + "\n```"
        assert _parse_template_reply(text) == VALID_TEMPLATE

    def test_prose_is_rejected(self):
        assert _parse_template_reply("Sure! Here is your workflow in plain English.") is None

    def test_stub_text_is_rejected(self):
        assert _parse_template_reply("[stub response - no provider]") is None

    def test_empty_reply_is_rejected(self):
        assert _parse_template_reply("") is None
        assert _parse_template_reply(None) is None

    def test_bad_json_is_rejected(self):
        assert _parse_template_reply('{"name": "x", "trigger": ') is None

    def test_list_root_is_rejected(self):
        assert _parse_template_reply(json.dumps([VALID_TEMPLATE])) is None

    @pytest.mark.parametrize("missing", ["name", "trigger", "steps"])
    def test_missing_required_key_is_rejected(self, missing):
        data = copy.deepcopy(VALID_TEMPLATE)
        del data[missing]
        assert _parse_template_reply(json.dumps(data)) is None

    def test_decision_word_no_longer_required(self):
        # The old code needed the literal word JSON in the decision text.
        assert _parse_template_reply(json.dumps(VALID_TEMPLATE)) is not None


# -- generate ----------------------------------------------------------------

class TestGenerate:
    def test_valid_json_reply_is_used(self, client, fake_llm):
        fake_llm(reply=json.dumps(VALID_TEMPLATE))
        r = _generate(client, prompt="A completely unrelated request about cats")
        assert r.status_code == 200, r.text
        assert r.json() == {**VALID_TEMPLATE, "template_id": "llm-template"}

    def test_fenced_json_reply_is_used(self, client, fake_llm):
        fake_llm(reply="```json\n" + json.dumps(VALID_TEMPLATE) + "\n```")
        r = _generate(client)
        assert r.json() == {**VALID_TEMPLATE, "template_id": "llm-template"}

    def test_prose_reply_falls_back_to_keyword_template(self, client, fake_llm):
        fake_llm(reply="Here is a plan: first build, then release.")
        r = _generate(client)
        assert r.status_code == 200
        assert r.json()["name"] == "Mine"
        assert r.json()["trigger"]["provider"] == "github"

    def test_stub_reply_falls_back(self, client, fake_llm):
        fake_llm(reply="[stub response - no provider]")
        r = _generate(client, prompt="jira ticket triage please")
        assert r.json()["trigger"]["provider"] == "jira"

    def test_llm_error_falls_back_not_500(self, client, fake_llm):
        fake_llm(error=RuntimeError("provider down"))
        r = _generate(client)
        assert r.status_code == 200
        assert r.json()["name"] == "Mine"

    def test_generic_prompt_uses_generic_fallback(self, client, fake_llm):
        fake_llm(reply="not json")
        r = _generate(client, prompt="something entirely different")
        assert r.json()["name"] == "Mine"
        assert r.json()["trigger"]["provider"] == "generic"

    def test_llm_is_called_with_the_prompt(self, client, fake_llm):
        llm = fake_llm(reply=json.dumps(VALID_TEMPLATE))
        _generate(client, prompt="Build a release flow for repo acme/api")
        assert len(llm.calls) == 1
        assert "acme/api" in llm.calls[0][1]

    def test_short_prompt_is_422(self, client, fake_llm):
        fake_llm(reply="{}")
        r = client.post("/api/builder/generate", json={"prompt": "short"})
        assert r.status_code == 422

    @pytest.mark.parametrize("prompt", [
        "github merge release workflow",
        "jira ticket triage workflow",
        "anything else at all, really",
    ])
    def test_every_fallback_passes_the_save_validators(self, client, fake_llm, prompt):
        fake_llm(reply="prose only")
        r = _generate(client, prompt=prompt)
        template = r.json()
        assert _validate_template_adapters(template) == []
        assert _validate_step_configs(template) == []


# -- fallback templates ------------------------------------------------------

class TestFallbackTemplates:
    @pytest.mark.parametrize("prompt", [
        "github merge",
        "jira ticket",
        "whatever is here",
    ])
    def test_validates_cleanly(self, prompt):
        tpl = _fallback_template(GenerationRequest(prompt=prompt))
        assert _validate_template_adapters(tpl) == []
        assert _validate_step_configs(tpl) == []

    @pytest.mark.parametrize("prompt", ["github merge", "jira ticket", "whatever is here"])
    def test_no_shell_steps(self, prompt):
        tpl = _fallback_template(GenerationRequest(prompt=prompt))
        for step in tpl["steps"]:
            assert step["adapter"] not in ("shell", "bob_shell")
            assert "script" not in step.get("config", {})

    @pytest.mark.parametrize("prompt", ["github merge", "jira ticket", "whatever is here"])
    def test_every_step_has_action_and_allowed_adapter(self, prompt):
        tpl = _fallback_template(GenerationRequest(prompt=prompt))
        for step in tpl["steps"]:
            assert step["action"]
            assert step["adapter"] in {"internal", "github", "jira", "ai"}

    def test_template_name_override_is_kept(self):
        tpl = _fallback_template(GenerationRequest(prompt="github merge", template_name="Custom"))
        assert tpl["name"] == "Custom"


# -- validate ----------------------------------------------------------------

class TestValidateEndpoint:
    def test_valid_template_is_valid(self, client):
        r = client.post("/api/builder/validate", json={"template_data": VALID_TEMPLATE})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "valid"
        assert body["violations"] == []

    def test_shell_template_is_invalid_with_violation(self, client):
        bad = copy.deepcopy(VALID_TEMPLATE)
        bad["steps"][0] = {"id": 1, "adapter": "shell", "action": "run",
                           "config": {"script": "build.sh"}, "board_stage": "EXECUTING"}
        r = client.post("/api/builder/validate", json={"template_data": bad})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "invalid"
        assert any("shell" in v for v in body["violations"])

    def test_bad_jira_config_is_invalid(self, client):
        bad = copy.deepcopy(VALID_TEMPLATE)
        bad["steps"][0] = {"id": 1, "adapter": "jira", "action": "list_tickets",
                           "config": {"not_a_field": 1}, "board_stage": "INTAKE"}
        r = client.post("/api/builder/validate", json={"template_data": bad})
        body = r.json()
        assert body["status"] == "invalid"
        assert body["violations"]

    def test_missing_field_is_400(self, client):
        r = client.post("/api/builder/validate", json={"template_data": {"name": "x"}})
        assert r.status_code == 400

    def test_empty_steps_is_400(self, client):
        data = copy.deepcopy(VALID_TEMPLATE)
        data["steps"] = []
        r = client.post("/api/builder/validate", json={"template_data": data})
        assert r.status_code == 400

    def test_every_fallback_validates_through_the_endpoint(self, client):
        for prompt in ("github merge", "jira ticket", "anything at all"):
            tpl = _fallback_template(GenerationRequest(prompt=prompt))
            body = client.post("/api/builder/validate", json={"template_data": tpl}).json()
            assert body["status"] == "valid", (prompt, body)


# -- template_id (P0-4) -------------------------------------------------------

class TestTemplateId:
    """POST /api/workflows/templates requires a template_id; the generate
    response must carry one, derived from the template name with the same
    slug rule BlueprintArchitect applies client-side, for the LLM path and
    every fallback template. Otherwise the WorkflowBuilder save always 400s."""

    def test_llm_path_gets_a_template_id(self, client, fake_llm):
        fake_llm(reply=json.dumps(VALID_TEMPLATE))
        r = _generate(client, prompt="a wholly unrelated request")
        assert r.json()["template_id"] == "llm-template"

    def test_llm_provided_template_id_is_replaced_by_the_derived_one(self, client, fake_llm):
        # The id is derived deterministically from the name; an LLM-emitted id
        # (which may be arbitrary) never reaches the save endpoint.
        template = {**VALID_TEMPLATE, "template_id": "TRUST ME"}
        fake_llm(reply=json.dumps(template))
        r = _generate(client, prompt="a wholly unrelated request")
        assert r.json()["template_id"] == "llm-template"

    @pytest.mark.parametrize("prompt,expected", [
        ("github merge release", "github-pr-review"),
        ("jira ticket triage", "jira-triage"),
        ("something entirely different", "custom-workflow"),
    ])
    def test_fallback_templates_get_their_slug(self, client, fake_llm, prompt, expected):
        fake_llm(reply="prose only")
        r = client.post("/api/builder/generate", json={"prompt": prompt})
        assert r.status_code == 200
        assert r.json()["template_id"] == expected

    def test_fallback_with_template_name_override_uses_that_name(self, client, fake_llm):
        fake_llm(reply="prose only")
        r = _generate(client)
        assert r.json()["name"] == "Mine"
        assert r.json()["template_id"] == "mine"

    @pytest.mark.parametrize("name,expected", [
        ("Simple", "simple"),
        ("  Padded Name  ", "padded-name"),
        ("Many -- Special __ Chars!!", "many-special-chars"),
        ("-leading and trailing-", "leading-and-trailing"),
        ("Ünïcödé nàme", "n-c-d-n-me"),  # non-ascii runs each collapse to one hyphen
        ("", "blueprint"),
        ("   ", "blueprint"),
        ("!!!", "blueprint"),
    ])
    def test_slug_rule_matches_the_client(self, name, expected):
        from api.builder_router import _template_id_from_name
        assert _template_id_from_name(name) == expected

    def test_none_name_falls_back(self):
        from api.builder_router import _template_id_from_name
        assert _template_id_from_name(None) == "blueprint"

    def test_response_shape_is_otherwise_unchanged(self, client, fake_llm):
        fake_llm(reply=json.dumps(VALID_TEMPLATE))
        r = _generate(client, prompt="a wholly unrelated request")
        body = r.json()
        assert set(body) == set(VALID_TEMPLATE) | {"template_id"}
