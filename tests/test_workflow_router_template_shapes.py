"""P1-3 / R15 / R16: template shape validation.

A template whose ``steps`` is not a list, or whose entries are not objects, must be
rejected with a 422 violation instead of being saved unvalidated. The B2 config
schema is also applied when the adapter is named only in ``config.adapter``.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.workflow_router import _validate_step_configs, _validate_template_adapters


@pytest.fixture
def client():
    return TestClient(app)


def _post(client, tid, **extra):
    body = {"template_id": tid, "name": "t", **extra}
    return client.post("/api/workflows/templates", json=body)


def _saved_ids(client):
    return {t.get("template_id") or t.get("id") for t in client.get("/api/workflows/templates").json()}


def _cleanup(client, tid):
    client.delete(f"/api/workflows/templates/{tid}")


# --------------------------------------------------------------------------
# steps shape (helpers)
# --------------------------------------------------------------------------
class TestStepsShapeHelpers:
    @pytest.mark.parametrize("steps", [{"a": 1}, "steps", 5, True, {"0": {"adapter": "shell"}}])
    def test_non_list_steps_is_a_violation(self, steps):
        violations = _validate_template_adapters({"steps": steps})
        assert violations and "steps" in violations[0]

    @pytest.mark.parametrize("template", [{}, {"steps": None}, {"steps": []}])
    def test_absent_null_or_empty_steps_is_still_allowed(self, template):
        assert _validate_template_adapters(template) == []
        assert _validate_step_configs(template) == []

    @pytest.mark.parametrize("entry", ["internal", 3, None, ["x"]])
    def test_non_dict_step_entry_is_a_violation(self, entry):
        violations = _validate_template_adapters({"steps": [entry]})
        assert violations and "object" in violations[0]

    def test_step_configs_helper_does_not_iterate_dict_keys(self):
        # Before the fix this iterated the keys and silently skipped them.
        assert _validate_step_configs({"steps": {"adapter": "internal"}}) == []

    def test_step_configs_helper_tolerates_non_dict_entries(self):
        assert _validate_step_configs({"steps": ["x", 1, None]}) == []


# --------------------------------------------------------------------------
# steps shape (route)
# --------------------------------------------------------------------------
class TestStepsShapeRoute:
    @pytest.mark.parametrize("steps", [{"a": 1}, "oops", 7, {"s1": {"adapter": "shell"}}])
    def test_non_list_steps_is_422_and_not_saved(self, client, steps):
        tid = "shape_nonlist"
        try:
            r = _post(client, tid, steps=steps)
            assert r.status_code == 422, r.status_code
            assert r.json()["detail"]["violations"]
            assert tid not in _saved_ids(client)
        finally:
            _cleanup(client, tid)

    @pytest.mark.parametrize("entry", ["internal", 3, None])
    def test_non_dict_entry_is_422(self, client, entry):
        tid = "shape_entry"
        try:
            r = _post(client, tid, steps=[entry])
            assert r.status_code == 422, r.status_code
        finally:
            _cleanup(client, tid)

    def test_valid_list_still_saves(self, client):
        tid = "shape_ok"
        try:
            r = _post(client, tid, steps=[{"id": 1, "adapter": "internal", "action": "list_items",
                                           "config": {"action": "list_items"}}])
            assert r.status_code == 200, r.json()
            assert tid in _saved_ids(client)  # proves _saved_ids can see a saved template
        finally:
            _cleanup(client, tid)

    def test_missing_steps_still_saves(self, client):
        tid = "shape_nosteps"
        try:
            r = _post(client, tid)
            assert r.status_code == 200, r.json()
        finally:
            _cleanup(client, tid)


# --------------------------------------------------------------------------
# config.adapter resolves the schema when step.adapter is empty
# --------------------------------------------------------------------------
class TestConfigAdapterSchema:
    def test_config_adapter_schema_applied_when_step_adapter_absent(self):
        step = {"id": 1, "config": {"adapter": "internal", "action": "nope"}}
        violations = _validate_step_configs({"steps": [step]})
        assert violations and "step 1" in violations[0] and "action" in violations[0]

    def test_config_adapter_schema_applied_when_step_adapter_empty_string(self):
        step = {"id": 2, "adapter": "", "config": {"adapter": "github", "per_page": 1000}}
        violations = _validate_step_configs({"steps": [step]})
        assert violations and "step 2" in violations[0]

    def test_config_adapter_is_case_and_space_insensitive(self):
        step = {"id": 3, "config": {"adapter": " Internal ", "action": "nope"}}
        assert _validate_step_configs({"steps": [step]})

    def test_valid_config_with_config_adapter_passes(self):
        step = {"id": 4, "config": {"adapter": "internal", "action": "list_items"}}
        assert _validate_step_configs({"steps": [step]}) == []

    def test_adapter_key_inside_config_is_not_an_extra_property_violation(self):
        # "adapter" itself is the selector and must not trip additionalProperties=False.
        step = {"id": 5, "config": {"adapter": "ai", "prompt": "hi"}}
        assert _validate_step_configs({"steps": [step]}) == []

    def test_config_adapter_selector_not_flagged_when_step_adapter_set(self):
        # Same selector key, same outcome whether it sits next to step.adapter or not.
        step = {"id": 9, "adapter": "internal", "config": {"adapter": "internal", "action": "list_items"}}
        assert _validate_step_configs({"steps": [step]}) == []

    def test_step_adapter_wins_over_config_adapter(self):
        # The internal schema applies (per_page is a github-only field), not github's.
        step = {"id": 6, "adapter": "internal", "config": {"action": "list_items", "per_page": 5}}
        assert _validate_step_configs({"steps": [step]})
        step = {"id": 6, "adapter": "internal", "config": {"adapter": "github", "per_page": 5}}
        assert _validate_step_configs({"steps": [step]})

    def test_non_string_config_adapter_does_not_raise(self):
        for bad in (None, 5, ["x"], {"a": 1}):
            _validate_step_configs({"steps": [{"id": 1, "config": {"adapter": bad}}]})

    def test_unknown_config_adapter_has_no_schema_and_is_skipped_by_b2(self):
        step = {"id": 7, "config": {"adapter": "no_such", "anything": 1}}
        assert _validate_step_configs({"steps": [step]}) == []

    def test_route_rejects_bad_config_for_config_adapter(self, client):
        tid = "shape_cfg_adapter"
        step = {"id": 1, "action": "x",
                "config": {"adapter": "internal", "action": "nope"}, "board_stage": "INTAKE"}
        try:
            r = _post(client, tid, steps=[step])
            assert r.status_code == 422, r.json()
            assert "config validation failed" in r.json()["detail"]["violations"][0]
        finally:
            _cleanup(client, tid)

    def test_route_accepts_good_config_for_config_adapter(self, client):
        tid = "shape_cfg_adapter_ok"
        step = {"id": 1, "action": "x",
                "config": {"adapter": "internal", "action": "list_items"}, "board_stage": "INTAKE"}
        try:
            r = _post(client, tid, steps=[step])
            assert r.status_code == 200, r.json()
        finally:
            _cleanup(client, tid)
