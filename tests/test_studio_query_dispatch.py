"""T5-pre1 / Gap 2: headless Query node must honor node.action + list/vector dispatch.

Gap (verified at HEAD 9a89fe7): `_execute_query_node` hardcoded `operator_id:
"fetch_resource"` and packed `node.action` into `config`, but OperatorRegistry
dispatches on `operator_id` (-> `fetch`) and never consults `action`. So the dec #28
list/vector actions added to the adapters (jira.list_tickets, internal.list_items,
...) were unreachable on the headless AND interactive preview path — FanOut would
see a non-list and iterate nothing.

These tests pin the fix: a Query node with action=`list_tickets` must call
`adapter.list_tickets(**params)` directly and store the returned list under
`output_ref`, so a downstream FanOut iterates real items. The dict-shaped
`list_items` return (`{"items": [...]}`) is reachable via a dot-path source.
"""
import asyncio
import unittest
from unittest.mock import Mock

from api.execution.studio_graph_engine import PathStepGraphEngine
from api.models.studio import (
    ExecutionState,
    QueryNode,
    NodeArchetype,
)
from api.operator_registry import OperatorRegistry
from api.secret_vault import SecretVault


def _make_engine():
    vault = Mock(spec=SecretVault)
    vault.get_secret.return_value = {"access_token": "fake_token"}
    registry = OperatorRegistry(vault=vault)
    import tempfile

    base_dir = tempfile.mkdtemp(prefix="studio_engine_test_")
    # Managers aren't exercised by the node handlers under test; pass them None
    # — the handlers only touch operator_registry + exec_state.
    engine = PathStepGraphEngine(
        base_dir=base_dir,
        operator_registry=registry,
        studio_graph_manager=None,
        skill_manager=None,
        run_manager=None,
    )
    return engine, registry


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestQueryNodeActionDispatch(unittest.TestCase):
    def setUp(self):
        self.engine, self.registry = _make_engine()

    def test_list_tickets_action_calls_adapter_method_not_fetch(self):
        """A Query node with action=list_tickets must dispatch to the adapter's
        list_tickets coroutine directly, not via fetch_resource->fetch."""
        adapter = self.registry.adapters["jira_adapter"]
        calls = {"fetch": 0, "list_tickets": 0}

        async def fake_fetch(resource_id=None, params=None):
            calls["fetch"] += 1
            return {}

        async def fake_list_tickets(jql="order by created DESC", max_results=50):
            calls["list_tickets"] += 1
            return [{"key": "PROJ-1"}, {"key": "PROJ-2"}]

        adapter.fetch = fake_fetch
        adapter.list_tickets = fake_list_tickets

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_tickets",
            params={"jql": "project = PROJ", "max_results": 5},
            output_ref="tickets",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )

        result = _run(self.engine._execute_query_node(exec_state, node))

        self.assertEqual(calls["fetch"], 0, "fetch must NOT be called for a list action")
        self.assertEqual(calls["list_tickets"], 1, "list_tickets must be called once")
        self.assertEqual(result, [{"key": "PROJ-1"}, {"key": "PROJ-2"}])
        # Engine caller writes result under output_ref; verify it lands in state.
        self.engine._write_to_state(exec_state.state, node.output_ref, result)
        self.assertEqual(exec_state.state["tickets"], [{"key": "PROJ-1"}, {"key": "PROJ-2"}])

    def test_list_items_dict_shape_reachable_via_dot_path(self):
        """internal.list_items returns {"items": [...]}. A FanOut whose source
        is '<output_ref>.items' must reach the list through _get_nested_value."""
        adapter = self.registry.adapters["internal_adapter"]

        async def fake_list_items(stage=None):
            return {"items": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}

        adapter.list_items = fake_list_items

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="internal_adapter",
            action="list_items",
            params={},
            output_ref="board",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        result = _run(self.engine._execute_query_node(exec_state, node))
        self.engine._write_to_state(exec_state.state, node.output_ref, result)

        # FanOut resolves source "board.items" -> the list inside the dict.
        resolved = self.engine._get_nested_value(exec_state.state, "board.items")
        self.assertEqual(resolved, [{"id": "A"}, {"id": "B"}, {"id": "C"}])
        self.assertIsInstance(resolved, list, "dot-path must resolve to the list FanOut can iterate")

    def test_unknown_action_falls_back_to_fetch_path(self):
        """An action that isn't a list/vector adapter method keeps the legacy
        fetch_resource->fetch path (do not break single-resource queries)."""
        adapter = self.registry.adapters["jira_adapter"]

        async def fake_fetch(resource_id=None, params=None):
            return {"key": "PROJ-1"}

        adapter.fetch = fake_fetch

        node = QueryNode(
            node_id="q1",
            name="q1",
            archetype=NodeArchetype.QUERY,
            adapter="jira_adapter",
            action="list_resources",
            params={},
            output_ref="one",
        )
        exec_state = ExecutionState(
            graph_id="g", run_id="r", state={}, run_log=[], undefined_queue=[], loop_stack=[]
        )
        result = _run(self.engine._execute_query_node(exec_state, node))
        self.assertEqual(result, {"key": "PROJ-1"})


if __name__ == "__main__":
    unittest.main()
