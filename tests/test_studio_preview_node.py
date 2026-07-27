"""Preview node endpoint coverage tests for Automation Studio.

Covers the /api/studio/preview-node endpoint and PathStepGraphEngine.preview_node
method across all four node archetypes: Query, FanOut, AITransform, ConditionalAction.

Tests validate:
- Variable placeholder resolution ({{variable}}) in query params
- Live data fetching and output_ref state persistence
- AITransform inline script / skill_ref execution with context wiring
- ConditionalAction condition evaluation and branch matching
- FanOut source list surfacing for card rendering
- Error handling (unknown adapters, security violations, runtime errors)
- State merging (updated_state preserves existing keys + adds output_ref)
"""
import asyncio
import tempfile
import unittest
from unittest.mock import Mock, AsyncMock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    QueryNode,
    FanOutNode,
    AITransformNode,
    ConditionalActionNode,
    NodeArchetype,
    Condition,
    ConditionType,
    CapabilityTier,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    """Create a fresh engine with temp dir and mocked dependencies."""
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    base_dir = tempfile.mkdtemp(prefix="studio_preview_test_")
    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=None,
        run_manager=None,
    )
    return engine, registry, base_dir


def _run(coro):
    """Run async coroutine in new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestPreviewNode(unittest.TestCase):
    """Tests for PathStepGraphEngine.preview_node covering all four node archetypes."""

    def setUp(self):
        self.engine, self.registry, self.base_dir = _make_engine()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.base_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # Node factory helpers
    # -------------------------------------------------------------------------
    def _query_node(self, adapter="internal_adapter", action="list_items", output_ref="items"):
        return QueryNode(
            node_id="q1",
            name="Query Tickets",
            archetype=NodeArchetype.QUERY,
            adapter=adapter,
            action=action,
            params={},
            output_ref=output_ref,
        )

    def _fanout_node(self, source="items", iterator_var="item"):
        return FanOutNode(
            node_id="f1",
            name="FanOut",
            archetype=NodeArchetype.FAN_OUT,
            loop_over={"source": source, "iterator_var": iterator_var},
        )

    def _ai_transform_node(
        self,
        script="result = input",
        skill_ref=None,
        input_ref="items",
        output_ref="transformed",
    ):
        return AITransformNode(
            node_id="a1",
            name="AI Transform",
            archetype=NodeArchetype.AI_TRANSFORM,
            script=script,
            skill_ref=skill_ref,
            input_ref=input_ref,
            output_ref=output_ref,
        )

    def _cond_node(
        self,
        condition_field="ticket.status",
        condition_value="Critical",
        condition_type=ConditionType.EQUALS,
    ):
        return ConditionalActionNode(
            node_id="c1",
            name="Conditional Action",
            archetype=NodeArchetype.CONDITIONAL_ACTION,
            condition=Condition(
                type=condition_type,
                field=condition_field,
                value=condition_value,
            ),
            routing_strategy="condition_first",
        )

    # -------------------------------------------------------------------------
    # Query node preview tests
    # -------------------------------------------------------------------------
    def test_preview_query_node_success_returns_list(self):
        """Query node preview fetches live data and returns list for card rendering."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"id": "1", "status": "Open"}, {"id": "2", "status": "Critical"}]})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="jira_tickets")
        execution_state = {}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        # internal_adapter.list_items returns {"items": [...]} dict
        self.assertIsInstance(result["result"], dict)
        self.assertIn("items", result["result"])
        self.assertEqual(len(result["result"]["items"]), 2)
        self.assertEqual(result["result"]["items"][0]["id"], "1")
        self.assertIn("jira_tickets", result["updated_state"])
        self.assertEqual(result["updated_state"]["jira_tickets"], result["result"])

    def test_preview_query_node_with_params_resolves_variables(self):
        """Query node params with {{variable}} placeholders resolve from execution_state."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"stage": "BACKLOG"}]})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="tickets")
        node.params = {"stage": "{{target_stage}}"}
        execution_state = {"target_stage": "BACKLOG"}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        adapter.list_items.assert_called_once_with(stage="BACKLOG")

    def test_preview_query_node_with_loop_context_priority(self):
        """loop_context takes priority over state for {{variable}} resolution."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"stage": "IN_PROGRESS"}]})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="tickets")
        node.params = {"stage": "{{target_stage}}"}
        # preview_node merges loop_context into state before calling _execute_query_node
        execution_state = {"target_stage": "BACKLOG"}  # Different from loop_context
        loop_context = {"target_stage": "IN_PROGRESS"}

        # We test the merged behavior by manually merging (what the UI would do)
        merged_state = {**execution_state, **loop_context}
        result = _run(self.engine.preview_node(node, merged_state))

        self.assertEqual(result["status"], "success")
        adapter.list_items.assert_called_once_with(stage="IN_PROGRESS")

    def test_preview_query_node_unknown_adapter_fallback(self):
        """Unknown adapter falls back to fetch_resource path and raises ValueError."""
        node = self._query_node(adapter="unknown_adapter", action="list_items", output_ref="items")
        execution_state = {}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "failed")
        self.assertIn("Unsupported adapter", result["error"])

    def test_preview_query_param_variable_missing_resolves_to_none(self):
        """Missing variable resolves to 'None' string (placeholder replaced with 'None')."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": []})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="tickets")
        node.params = {"stage": "{{missing_var}}"}
        execution_state = {"other": "value"}

        result = _run(self.engine.preview_node(node, execution_state))

        # Missing variable resolves to 'None' string
        adapter.list_items.assert_called_once_with(stage="None")

    def test_preview_query_multiple_params_all_resolved(self):
        """Multiple params with variables all resolve correctly."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"stage": "BACKLOG"}]})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="tickets")
        node.params = {"stage": "{{stage}}", "limit": "{{max_results}}"}
        execution_state = {"stage": "BACKLOG", "max_results": "50"}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        adapter.list_items.assert_called_once_with(stage="BACKLOG", limit="50")

    # -------------------------------------------------------------------------
    # AITransform node preview tests
    # -------------------------------------------------------------------------
    def test_preview_ai_transform_inline_script_success(self):
        """AITransform with inline script executes and returns transformed result."""
        node = self._ai_transform_node(
            script="result = {'processed': True, 'count': len(input)}",
            input_ref="items",
            output_ref="transformed",
        )
        execution_state = {"items": [{"id": "1"}, {"id": "2"}]}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["processed"], True)
        self.assertEqual(result["result"]["count"], 2)
        self.assertIn("transformed", result["updated_state"])

    def test_preview_ai_transform_accesses_state_and_loop(self):
        """AITransform script can access state, input, and loop context."""
        node = self._ai_transform_node(
            script="result = {'from_input': input[0]['id'], 'from_state': state['config'], 'from_loop': loop.get('item_id')}",
            input_ref="items",
            output_ref="out",
        )
        execution_state = {"config": "GLOBAL_CFG", "items": [{"id": "ITEM-1"}]}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["from_input"], "ITEM-1")
        self.assertEqual(result["result"]["from_state"], "GLOBAL_CFG")

    def test_preview_ai_transform_no_script_or_skill_fails(self):
        """AITransform with neither script nor skill_ref fails."""
        node = self._ai_transform_node(script=None)
        node.script = None
        node.skill_ref = None
        execution_state = {"items": []}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "failed")
        self.assertIn("neither script nor skill_ref", result["error"])

    def test_preview_ai_transform_security_error(self):
        """Blocked import (os) raises SecurityError."""
        node = self._ai_transform_node(script="import os\nresult = 'x'")
        execution_state = {"items": []}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "failed")
        self.assertIn("Blocked import due to security policy", result["error"] or "")
        self.assertIn("os", result["error"] or "")

    def test_preview_ai_transform_dependency_error(self):
        """Non-whitelisted import (pandas) raises DependencyRequiredError."""
        node = self._ai_transform_node(script="import pandas\nresult = 'x'")
        execution_state = {"items": []}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "failed")
        self.assertIn("Required dependency not installed", result["error"] or "")
        self.assertIn("pandas", result["error"] or "")

    def test_preview_ai_transform_runtime_error(self):
        """Script runtime error raises SafeExecutorError."""
        node = self._ai_transform_node(script="result = 1 / 0")
        execution_state = {"items": []}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "failed")
        self.assertIn("Error during execution", result["error"] or "")
        self.assertIn("division by zero", result["error"].lower())

    # -------------------------------------------------------------------------
    # ConditionalAction node preview tests
    # -------------------------------------------------------------------------
    def test_preview_cond_action_true_branch(self):
        """Condition matches -> matched_branch='true'."""
        node = self._cond_node(condition_field="ticket.status", condition_value="Critical")
        execution_state = {"ticket": {"status": "Critical", "id": "TKT-1"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "true")

    def test_preview_cond_action_false_branch(self):
        """Condition doesn't match -> matched_branch='false'."""
        node = self._cond_node(condition_field="ticket.status", condition_value="Critical")
        execution_state = {"ticket": {"status": "Low", "id": "TKT-2"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "false")

    def test_preview_cond_action_dot_path_resolution(self):
        """Condition field supports dot-path into nested state."""
        node = self._cond_node(condition_field="extracted_fields.os_distro", condition_value="brotli")
        execution_state = {"extracted_fields": {"os_distro": "brotli", "version": "1.2.3"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "true")

    def test_preview_cond_action_exists_type(self):
        """EXISTS condition checks field presence (value ignored)."""
        node = self._cond_node(condition_field="ticket.assignee", condition_value="")
        node.condition = Condition(type=ConditionType.EXISTS, field="ticket.assignee", value="")

        execution_state = {"ticket": {"status": "Open", "assignee": "user123"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "true")

    def test_preview_cond_action_exists_false_when_missing(self):
        """EXISTS condition is false when field is missing."""
        node = self._cond_node(condition_field="ticket.assignee", condition_value="")
        node.condition = Condition(type=ConditionType.EXISTS, field="ticket.assignee", value="")

        execution_state = {"ticket": {"status": "Open"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "false")

    # -------------------------------------------------------------------------
    # FanOut node preview tests
    # -------------------------------------------------------------------------
    def test_preview_fanout_returns_source_list(self):
        """FanOut preview returns the source list for card rendering."""
        node = self._fanout_node(source="items", iterator_var="item")
        execution_state = {"items": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertIsInstance(result["result"], list)
        self.assertEqual(len(result["result"]), 3)

    def test_preview_fanout_source_missing_returns_none(self):
        """FanOut with missing source returns None (no list to iterate)."""
        node = self._fanout_node(source="nonexistent", iterator_var="item")
        execution_state = {"other": "data"}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertIsNone(result["result"])

    def test_preview_fanout_source_not_list_returns_value(self):
        """FanOut with non-list source returns the value as-is."""
        node = self._fanout_node(source="single_item", iterator_var="item")
        execution_state = {"single_item": {"id": "only"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], {"id": "only"})

    # -------------------------------------------------------------------------
    # Variable placeholder resolution integration tests
    # -------------------------------------------------------------------------
    def test_preview_query_param_variable_resolution_with_nested_dot_path(self):
        """Query params can use {{variable}} with dot-path from nested state."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"stage": "BACKLOG"}]})

        node = self._query_node(adapter="internal_adapter", action="list_items", output_ref="tickets")
        node.params = {"stage": "{{config.stage}}"}
        execution_state = {"config": {"stage": "BACKLOG", "project": "OPS"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        adapter.list_items.assert_called_once_with(stage="BACKLOG")

    # -------------------------------------------------------------------------
    # State persistence across previews (output_ref written to updated_state)
    # -------------------------------------------------------------------------
    def test_preview_updates_state_with_output_ref(self):
        """Preview writes node output to updated_state using output_ref."""
        adapter = self.registry.adapters["internal_adapter"]
        adapter.list_items = AsyncMock(return_value={"items": [{"id": "A"}]})

        node = self._query_node(output_ref="my_output")
        execution_state = {"existing": "value"}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertIn("my_output", result["updated_state"])
        self.assertEqual(result["updated_state"]["my_output"], {"items": [{"id": "A"}]})
        self.assertEqual(result["updated_state"]["existing"], "value")

    def test_preview_ai_transform_writes_output_ref(self):
        """AITransform preview writes result to output_ref in updated_state."""
        node = self._ai_transform_node(
            script="result = {'key': 'value'}",
            input_ref="items",
            output_ref="transformed",
        )
        execution_state = {"items": []}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertIn("transformed", result["updated_state"])
        self.assertEqual(result["updated_state"]["transformed"], {"key": "value"})

    def test_preview_cond_action_no_output_ref(self):
        """ConditionalAction has no output_ref; state not modified."""
        node = self._cond_node()
        execution_state = {"ticket": {"status": "Critical"}}

        result = _run(self.engine.preview_node(node, execution_state))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["matched_branch"], "true")
        self.assertEqual(result["updated_state"], execution_state)

    # -------------------------------------------------------------------------
    # Error handling
    # -------------------------------------------------------------------------
    # Note: The /preview-node endpoint validates the node via TypeAdapter(StudioNode)
    # before passing to the engine, so unknown archetypes are caught at the API layer (422).
    # The engine dispatch would only see valid archetypes. Testing the engine's
    # ValueError for unknown archetypes would require bypassing the API validation.
    # We test the API validation in test_studio_router_endpoints.py instead.


if __name__ == "__main__":
    unittest.main()