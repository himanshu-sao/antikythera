"""Canonical adapter fallback (post-arc-A coordinator item).

Stored templates name adapters canonically (internal, github, jira, ai,
bob_shell) while integrations.json holds free-form names. ``execute_action``
now falls back to the canonical adapter module when no integration with that
name exists. Also covers the extended action map (internal verbs -> execute,
analyze) and the config fallback for workflow steps (config at the top level,
no "arguments" wrapper). The end-to-end test runs a stored AUTO-MOVE-TEST
shaped template through the real IntegrationHub and the real internal adapter
against the conftest-isolated state manager.
"""

import pytest

from api.integration_hub import CANONICAL_ADAPTERS, IntegrationHub


@pytest.fixture
def hub(tmp_path):
    return IntegrationHub(str(tmp_path))


class TestCanonicalFallback:
    def test_unknown_name_still_raises(self, hub):
        with pytest.raises(Exception, match="Integration nope not found"):
            hub.execute_action("nope", "fetch_resource", {})

    def test_canonical_names_resolve(self, hub):
        for name in ("internal", "github", "jira", "ai", "bob_shell"):
            assert name in CANONICAL_ADAPTERS

    def test_case_and_whitespace_are_normalised(self, hub, monkeypatch):
        captured = {}

        def fake_native(integration, action, params, secrets):
            captured.update(integration)
            return {"status": "success", "result": None, "logs": ""}

        monkeypatch.setattr(hub, "_execute_native", fake_native)
        hub.execute_action("  INTERNAL ", "list_items", {})
        assert captured["name"] == "internal"
        assert captured["config"]["adapter_module"] == "api.adapters.internal"
        assert captured["status"] == "canonical"

    def test_real_integration_wins_over_the_fallback(self, hub, monkeypatch):
        captured = {}

        def fake_native(integration, action, params, secrets):
            captured.update(integration)
            return {"status": "success", "result": None, "logs": ""}

        monkeypatch.setattr(hub, "_execute_native", fake_native)
        assert hub.add_integration("github", "native", {"adapter_module": "t8_fake_native_adapter"})
        hub.execute_action("github", "fetch_resource", {})
        assert captured["config"]["adapter_module"] == "t8_fake_native_adapter"
        assert captured.get("status") != "canonical"

    def test_synthetic_record_is_not_persisted(self, hub, monkeypatch):
        def fake_native(integration, action, params, secrets):
            return {"status": "success", "result": None, "logs": ""}

        monkeypatch.setattr(hub, "_execute_native", fake_native)
        hub.execute_action("internal", "list_items", {})
        # update_status must not write the synthetic record.
        assert "internal" not in hub._load_config()

    def test_bob_shell_fallback_logs_a_warning(self, hub, monkeypatch, caplog):
        def fake_native(integration, action, params, secrets):
            return {"status": "success", "result": None, "logs": ""}

        monkeypatch.setattr(hub, "_execute_native", fake_native)
        with caplog.at_level("WARNING", logger="backend"):
            hub.execute_action("bob_shell", "fetch_resource", {})
        assert any("execution-capable" in r.message for r in caplog.records)


class TestActionMap:
    def test_internal_verbs_map_to_execute(self):
        for verb in ("move_item", "add_comment"):
            assert IntegrationHub._ACTION_MAP[verb] == "execute"

    def test_analyze_maps_to_analyze(self):
        assert IntegrationHub._ACTION_MAP["analyze"] == "analyze"

    def test_builder_verbs_have_identity_entries(self):
        # P0-3: the builder fallback templates emit these actions; without an
        # entry each one failed with "Unsupported action".
        for verb in ("list_items", "list_repos", "list_pull_requests", "list_tickets",
                     "list_projects", "update", "execute"):
            assert IntegrationHub._ACTION_MAP[verb] == verb


class TestInternalEndToEnd:
    """Real hub + real internal adapter + the conftest-isolated state."""

    def _state_manager(self):
        from api.main import get_state_manager
        return get_state_manager()

    def test_move_item_moves_the_board_item(self, hub):
        sm = self._state_manager()
        assert sm.kanban.create_item("RUN-TEST-ITEM", "Run test item")
        assert sm.kanban.update_item("RUN-TEST-ITEM", {"stage": "INTAKE"})

        res = hub.execute_action("internal", "move_item", {
            "action": "move_item", "item_id": "RUN-TEST-ITEM", "new_stage": "REFINEMENT",
        })
        assert res["status"] == "success"
        item = sm.kanban.get_item_details("RUN-TEST-ITEM")
        assert item["stage"] == "REFINEMENT"

    def test_stored_shape_template_runs_to_completion(self, hub):
        from api.escalation_manager import EscalationManager
        from api.execution_engine import ExecutionEngine
        from api.retry_manager import RetryManager

        sm = self._state_manager()
        assert sm.kanban.create_item("RUN-TEST-ITEM", "Run test item")
        assert sm.kanban.update_item("RUN-TEST-ITEM", {"stage": "INTAKE"})

        # The stored AUTO-MOVE-TEST shape: no top-level type or adapter; the
        # adapter is implied by config.action (the old engine defaulted to
        # INTERNAL) and migrate_step promotes it.
        template = {
            "name": "Auto move test",
            "description": "stored shape",
            "trigger": {"type": "manual"},
            "steps": [
                {
                    "step_id": "S1",
                    "name": "Move to Refinement",
                    "category": "ACTION",
                    "config": {
                        "action": "move_item",
                        "new_stage": "REFINEMENT",
                        "item_id": "RUN-TEST-ITEM",
                    },
                }
            ],
        }
        assert sm.templates.save_template("AUTO-MOVE-TEST", template)

        engine = ExecutionEngine(sm, hub, EscalationManager(sm), RetryManager(sm))
        run_id = engine.start_run("AUTO-MOVE-TEST", {})
        run = sm.runs.get_run(run_id)
        assert run["status"] == "COMPLETED", run
        assert sm.kanban.get_item_details("RUN-TEST-ITEM")["stage"] == "REFINEMENT"
        assert "internal" not in hub._load_config()

    def test_internal_list_items_step_still_runs(self, hub):
        # Regression for the list_items identity entry: the internal-adapter
        # step convention carries an "action" key in the config (the save-time
        # schema requires it), which is dispatch metadata and must not be
        # passed to the adapter's list_items method as a keyword.
        sm = self._state_manager()
        assert sm.kanban.create_item("RUN-TEST-ITEM", "Run test item")
        assert sm.kanban.update_item("RUN-TEST-ITEM", {"stage": "REFINEMENT"})

        res = hub.execute_action("internal", "list_items",
                                 {"action": "list_items", "stage": "REFINEMENT"})
        assert res["status"] == "success", res
        titles = [i.get("title") for i in res["result"]["items"]]
        assert "Run test item" in titles


class TestAiAdapter:
    def test_analyze_delegates_to_the_shared_ai_adapter(self, hub, monkeypatch):
        import api.ai_adapter as ai_adapter_module

        recorded = {}

        class _FakeAIAdapter:
            def __init__(self, *a, **k):
                pass

            def analyze(self, prompt, context_data, patterns=None):
                recorded.update(prompt=prompt, context=context_data, patterns=patterns)
                return {"decision": "ok"}

        monkeypatch.setattr(ai_adapter_module, "AIAdapter", _FakeAIAdapter)
        res = hub.execute_action("ai", "analyze", {
            "prompt": "summarise", "context": {"ticket": "PROJ-1"},
        })
        assert res["status"] == "success"
        assert recorded["prompt"] == "summarise"
        assert recorded["context"] == {"ticket": "PROJ-1"}
        assert res["result"] == {"decision": "ok"}
